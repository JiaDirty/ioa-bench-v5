import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.construct_dispatch import (
    DISPATCH_VERSION,
    RUNNERS,
    execute_construct_case_sync,
    frozen_case_to_runtime_input,
)
from ioabench.runtime.offline_run import SUITES

ROOT = Path(__file__).parents[2]
PROFILE = ModelProfile("mock", "dispatcher-check", {"tools": True}, {})


# Single source of truth for the frozen dataset versions (T311's newest frozen
# release is 2.0.0 and deliberately unmapped there, hence the fallback below).
from ioabench.frozen_versions import FROZEN_VERSIONS as _AUTHORITATIVE_VERSIONS  # noqa: E402
_required = {"T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333", "T341", "T342",
             "T343", "T351", "T352", "T353", "T361", "T362", "T363"}
_missing = sorted(_required - set(_AUTHORITATIVE_VERSIONS))
if _missing:
    raise SystemExit(f"FROZEN_VERSIONS is missing suites {_missing}; refusing silent legacy-dataset fallback")
FROZEN_VERSIONS = {suite: _AUTHORITATIVE_VERSIONS.get(suite, "2.0.0") for suite in SUITES}


def frozen_case(suite: str) -> dict:
    version = FROZEN_VERSIONS.get(suite, "dev-mini")
    dataset = ROOT / "data" / "datasets" / suite / version / "cases.jsonl"
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    risk = next((case for case in cases if case.get("provenance", {}).get("condition") == "RISK"), cases[0])
    return risk


@pytest.mark.parametrize("suite", SUITES)
def test_frozen_cases_execute_through_the_construct_dispatcher(suite):
    case = frozen_case(suite)
    from ioabench.runtime.construct_dispatch import resolve_mock_model
    result = execute_construct_case_sync(
        ROOT, suite, case, resolve_mock_model(suite), PROFILE, run_id=f"{suite}-dispatch-check")
    assert result["status"] == "COMPLETED"
    assert result["replay"]["scenario"]["test_id"] == suite
    # Legacy v1 frozen T361-T363 cases predate the causal world payloads, so
    # they execute degenerately with zero model calls until Phase B freezes
    # v2 datasets; every other suite must show real model interaction.
    if suite not in {"T361", "T362", "T363"}:
        assert result["replay"]["model_records"]
    assert result["replay"]["world_snapshot"]
    dispatch = result["dispatch"]
    assert dispatch["dispatch_version"] == DISPATCH_VERSION
    assert dispatch["case_id"] == case["candidate_id"]
    assert dispatch["case_sha256"] == canonical_sha256(case)
    assert dispatch["frozen_case_executed_directly"] is True
    assert dispatch["runtime_version"]
    if suite in {"T361", "T362", "T363"}:
        assert result["eligibility"] == "SIMULATION_ONLY"
        assert result["replay"]["scenario"]["simulation_only"] is True


def test_dispatcher_executes_the_frozen_case_without_regeneration(monkeypatch):
    import ioabench.suites.t352.generation as t352_generation

    def forbidden(*args, **kwargs):
        raise AssertionError("dispatcher regenerated a frozen case instead of executing it")

    monkeypatch.setattr(t352_generation.T352Generator, "generate", forbidden)
    case = frozen_case("T352")
    from ioabench.runtime.construct_dispatch import resolve_mock_model
    result = execute_construct_case_sync(
        ROOT, "T352", case, resolve_mock_model("T352"), PROFILE, run_id="T352-dispatch-frozen")
    assert result["status"] == "COMPLETED"
    assert result["dispatch"]["case_sha256"] == canonical_sha256(case)


def test_dispatcher_rejects_unknown_suite():
    case = frozen_case("T312")
    result = execute_construct_case_sync(ROOT, "T999", case, object(), PROFILE, run_id="bad")
    assert result["status"] == "FAILED"
    assert result["infrastructure_failure"] is False
    assert result["error_class"] == "ValueError"


def test_frozen_case_view_preserves_oracle_bytes_and_provenance():
    case = frozen_case("T351")
    view = frozen_case_to_runtime_input(case)
    assert view["candidate_id"] == case["candidate_id"]
    assert view["condition"] == case["provenance"]["condition"]
    assert json.loads(view["ground_truth"]["_content"].decode("utf-8")) == case["oracle_payload"]
    assert view["sut_payload"] == case["sut_payload"]


def test_formal_run_path_uses_dispatcher_not_legacy_mock_executor():
    cli_source = (ROOT / "src" / "ioabench" / "cli.py").read_text(encoding="utf-8")
    assert "execute_mock_case" not in cli_source
    assert "execute_construct_case_strict(" in cli_source
    legacy_source = (ROOT / "src" / "ioabench" / "runtime" / "offline_run.py").read_text(encoding="utf-8")
    assert "execute_mock_case" in legacy_source  # retained for historical replay only
    assert set(RUNNERS) == set(SUITES)
