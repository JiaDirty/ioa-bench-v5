"""P1 acceptance tests: the formal opt-in dynamic runner executes T321-DYNA, T321-DYNB,
T312-DYNA, T352-DYNA (multi-round allocation machine) and T331-DYNA (multi-agent fan-out
cascade) with the mandatory monitor chain, journal, exposure/opportunity and score — without
touching the frozen 18-suite registry. T352/T331 prove the runner handles multi-round,
multi-actor state machines, not only single-step tool interactions."""
from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ioabench.models import ModelProfile, ModelResponse
from ioabench.errors import ProviderTransientError
from ioabench.v5.dynamic import runner as dynamic_runner
from ioabench.v5.dynamic.runner import RUNNER_VERSION, adapter_fingerprint, run_dynamic_case
from ioabench.v5.dynamic import t321_slice, t321_slice_b, t312_slice, t331_slice, t352_slice

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def _first_pair(module):
    return module.generate(seed=5, families=1)[0]


@pytest.mark.parametrize("module", [t321_slice, t321_slice_b, t312_slice, t352_slice, t331_slice],
                         ids=["T321-DYNA", "T321-DYNB", "T312-DYNA", "T352-DYNA", "T331-DYNA"])
def test_dynamic_runner_full_chain(module, tmp_path: Path) -> None:
    control, risk = _first_pair(module)
    for case in (control, risk):
        result = run_dynamic_case(tmp_path, case, module,
                                  module.policies()["witness"], PROFILE,
                                  run_id=f"runner-test-{module.SLICE_ID}",
                                  parameters={"temperature": 0.0},
                                  timing_rules=getattr(module, "TIMING_RULES", ()))
        assert result["status"] == "COMPLETED", result.get("error")
        assert result["scientifically_eligible"] is True, result["ineligibility_reasons"]
        assert result["monitor_report"]["ledger_integrity"]["passed"]
        assert result["exposure"]["exposed"] and result["exposure"]["opportunity"]
        assert result["score"] is not None and result["score"]["safety"] == "SAFE"
        assert result["versions"]["runner"] == RUNNER_VERSION
        assert result["adapter"]["adapter_module"].endswith(module.__name__)


def test_t352_multi_round_machine_runs_all_four_rounds(tmp_path: Path) -> None:
    """T352 is a four-round two-allocator state machine: the runner must drive ALL rounds to
    completion (allocate+rate for both allocators each round) with a green monitor — proof it
    handles multi-round multi-actor episodes, not only single-step interactions."""
    control, _ = _first_pair(t352_slice)
    result = run_dynamic_case(tmp_path, control, t352_slice,
                              t352_slice.policies()["witness"], PROFILE,
                              run_id="runner-t352-rounds",
                              parameters={"temperature": 0.0},
                              timing_rules=t352_slice.TIMING_RULES)
    assert result["status"] == "COMPLETED", result.get("error")
    allocations = result["trace"]["final_state"]["allocations"]
    assert len(allocations) == 4, f"expected all 4 rounds, got {sorted(allocations)}"
    for round_no, alloc in allocations.items():
        assert set(alloc) == {"allocator_1", "allocator_2"}
    ratings = result["trace"]["final_state"]["ratings"]
    assert len(ratings) == 4
    monitor = result["monitor_report"]
    assert monitor["ledger_integrity"]["passed"] and monitor["ledger_integrity"]["legacy_mode"] is False


def test_t331_multi_agent_cascade_runs_full_fan_out(tmp_path: Path) -> None:
    """T331 is a three-operator fan-out cascade: the runner must drive all three agents and the
    propagation must reach both terminals with a green monitor."""
    control, _ = _first_pair(t331_slice)
    result = run_dynamic_case(tmp_path, control, t331_slice,
                              t331_slice.policies()["witness"], PROFILE,
                              run_id="runner-t331-fanout",
                              parameters={"temperature": 0.0},
                              timing_rules=t331_slice.TIMING_RULES)
    assert result["status"] == "COMPLETED", result.get("error")
    actors = {a["actor"] for a in result["trace"]["actions"]}
    assert actors == {"node_a", "node_b1", "node_b2"}
    forwarded = [f for f in result["trace"]["final_state"]["forwarded"] if f["from"] == "node_a"]
    assert {f["to"] for f in forwarded} == {"node_b1", "node_b2"}
    assert result["monitor_report"]["message_flow"]["undelivered_enqueues"] == 0
    assert result["scientifically_eligible"] is True


def test_dynamic_runner_records_monitor_failure_as_ineligible(tmp_path: Path, monkeypatch) -> None:
    """A deliberately damaged trace (missing execution event) must be marked ineligible —
    never presented as a valid scientific sample."""
    control, _ = _first_pair(t321_slice)
    original = dynamic_runner.await_run_episode

    def damaged_episode(*args, **kwargs):
        trace = original(*args, **kwargs)
        trace.events = [e for e in trace.events
                        if not (e["kind"] == "tool_executed" and e["payload"]["action_seq"] == 1)]
        return trace

    monkeypatch.setattr(dynamic_runner, "await_run_episode", damaged_episode)
    result = run_dynamic_case(tmp_path, control, t321_slice,
                              t321_slice.policies()["witness"], PROFILE,
                              run_id="runner-ineligible-test",
                              parameters={"temperature": 0.0},
                              timing_rules=t321_slice.TIMING_RULES)
    assert result["scientifically_eligible"] is False
    assert not result["monitor_report"]["ledger_integrity"]["passed"]
    assert "LEDGER_INTEGRITY_FAILED" in result["ineligibility_reasons"]


def test_dynamic_runner_invalid_model_output_is_ineligible(tmp_path: Path) -> None:
    control, _ = _first_pair(t321_slice)

    class EmptyOutput:
        async def generate(self, profile, request):
            return ModelResponse(text="", finish_reason="stop")

    result = run_dynamic_case(tmp_path, control, t321_slice, EmptyOutput(), PROFILE,
                              run_id="runner-invalid-output", parameters={})
    assert result["status"] == "INVALID_MODEL_OUTPUT"
    assert result["outcome"]["eligibility"] == "INVALID_MODEL_OUTPUT"
    assert result["scientifically_eligible"] is False
    assert result["ineligibility_reasons"] == ["INVALID_MODEL_OUTPUT"]


def test_dynamic_runner_keeps_journal_in_active_async_context(tmp_path: Path) -> None:
    control, _ = _first_pair(t321_slice)
    witness = t321_slice.policies()["witness"]

    class Interrupted:
        count = 0

        async def generate(self, profile, request):
            self.count += 1
            if self.count == 2:
                raise ProviderTransientError("channel interrupted after first behavior")
            return await witness.generate(profile, request)

    async def execute():
        return run_dynamic_case(tmp_path, control, t321_slice, Interrupted(), PROFILE,
                                run_id="async-interruption", parameters={})

    result = asyncio.run(execute())
    assert result["status"] == "INFRA_INTERRUPTED"
    assert result["scientifically_eligible"] is False
    assert result["ineligibility_reasons"] == ["INFRA_INTERRUPTED"]
    assert result["model_calls"] == 1
    assert result["monitor_report"]["status"] == "NOT_AVAILABLE"
    journal = tmp_path / result["attempt_journal"]["path"]
    entries = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 2 and entries[1]["kind"] == "model_record"
    assert entries[1]["record"]["response"]["tool_calls"]


@pytest.mark.parametrize("leakage", [False, True], ids=["before-model-response", "leaking-opening"])
def test_failure_rows_do_not_claim_complete_monitor_evidence(tmp_path: Path, leakage: bool) -> None:
    control, _ = _first_pair(t321_slice)
    if leakage:
        control = replace(control, world={**control.world, "business_context": "hidden oracle facts"})

    class Unavailable:
        async def generate(self, profile, request):
            raise ProviderTransientError("channel unavailable")

    result = run_dynamic_case(tmp_path, control, t321_slice, Unavailable(), PROFILE,
                              run_id="unavailable", parameters={})
    expected = "LEAKAGE_BLOCKED" if leakage else "RETRYABLE_INFRA_FAILURE"
    assert result["status"] == expected
    assert result["outcome"]["eligibility"] == expected
    assert result["scientifically_eligible"] is False
    assert result["ineligibility_reasons"] == [expected]
    assert result["model_calls"] == 0
    assert result["monitor_report"]["ledger_integrity"]["passed"] is None


def test_dynamic_runner_refuses_mismatched_adapter_before_attempt(tmp_path: Path) -> None:
    control, _ = _first_pair(t321_slice)
    with pytest.raises(ValueError, match="does not match dynamic adapter"):
        run_dynamic_case(tmp_path, control, t312_slice, t312_slice.policies()["witness"], PROFILE,
                         run_id="mismatch", parameters={})
    assert not (tmp_path / "data").exists()


def test_default_timing_rules_record_behavior_violation_without_excluding_it(tmp_path: Path) -> None:
    _, risk = _first_pair(t321_slice)
    result = run_dynamic_case(tmp_path, risk, t321_slice, t321_slice.policies()["naive"], PROFILE,
                              run_id="default-timing", parameters={})
    timing = result["monitor_report"]["timing_properties"]
    assert timing["rules"] == [rule.name for rule in t321_slice.TIMING_RULES]
    assert timing["violations"] and not timing["indeterminate"]
    assert result["scientifically_eligible"] is True
    assert result["outcome"]["eligibility"] == "ELIGIBLE"


def test_adapter_fingerprint_is_recorded() -> None:
    fp = adapter_fingerprint(t321_slice)
    assert fp["suite_id"] == "T321-DYNA"
    assert fp["runner_version"] == RUNNER_VERSION
    assert fp["engine_version"]
    assert fp["scenario_version"].startswith("t321-dyna")
