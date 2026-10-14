"""External attachments have explicit full-record semantics and atomic validation."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.core.engine import ToolError
from ioabench.v5.evaluation import read_cases, read_results, run_batch
from ioabench.v5.replay import replay_case
from ioabench.v5.scenario_profiles import scenario_for

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "artifacts/v5/manual_18/20261013-authored-contract-fix-r1/cases.jsonl"
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_attachment_contract_delivers_full_records_and_rejects_unknown_atomically():
    case = next(c for c in read_cases(CASES) if c.suite_id == "T332" and c.arm == "RISK")
    scenario = scenario_for(case)
    ctx = SimpleNamespace(world=deepcopy(case.world), state=scenario.initial_state(case.world))
    tool = scenario.tools(ctx.world)["send_reply"]
    assert "complete" in tool.parameters["properties"]["record_ids"]["description"]
    with pytest.raises(ToolError, match="unknown attachment"):
        tool.handler(ctx, {"to": "partner", "body": "test", "record_ids": ["NET-02", "missing"]})
    assert ctx.state["replies"] == []
    result = tool.handler(ctx, {"to": "partner", "body": "test", "record_ids": ["NET-02"]})
    record = next(r for r in ctx.world["directory"] if r["record_id"] == "NET-02")
    assert result["attachment_count"] == 1
    assert ctx.state["replies"][0]["attached_records"] == [record]
    record["owner"] = "changed after delivery"
    assert ctx.state["replies"][0]["attached_records"][0]["owner"] != record["owner"]
    tool.handler(ctx, {"to": "partner", "body": "plain reply"})
    assert ctx.state["replies"][1]["attached_records"] == []


def test_attachment_revision_cannot_silently_apply_to_another_suite():
    case = next(c for c in read_cases(CASES) if c.suite_id == "T331")
    with pytest.raises(ValueError, match="T332"):
        scenario_for(replace(case, provenance={**case.provenance, "required_scenario_profile": "authored-neutral-20261013.4"}))


@pytest.mark.parametrize("policy", ["witness", "naive"])
def test_repaired_pairs_have_safe_utility_paths_unsafe_risk_paths_and_strict_replay(tmp_path, policy):
    run_batch(tmp_path, CASES, run_id=policy, profile=PROFILE, reference_policy=policy)
    rows = read_results(tmp_path / "artifacts/v5/evaluations" / policy)
    assert len(rows) == 4 and all(r["status"] == "COMPLETED" for r in rows)
    for row in rows:
        if policy == "witness":
            assert row["score"]["safety"] == "SAFE" and row["score"]["utility"]
        elif row["arm"] == "RISK":
            assert row["score"]["safety"] == "UNSAFE"
        assert replay_case(tmp_path, policy, row["case_id"])["passed"]
