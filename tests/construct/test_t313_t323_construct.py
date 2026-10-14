import asyncio
from dataclasses import asdict
from copy import deepcopy
from pathlib import Path

from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.delegation_provenance import DelegationBaseline, build_delegation_case_from_skeleton, build_delegation_fixture, execute_delegation
from ioabench.suites.t313.generation import T313Generator
from ioabench.suites.t323.generation import T323Generator

ROOT = Path(__file__).parents[2]


def run(suite, policy, case=None, model=None):
    case = case or build_delegation_fixture(suite)
    return asyncio.run(execute_delegation(ROOT, case, model or DelegationBaseline(policy), ModelProfile("mock", "offline-chain", {"tools": True}, {}), run_id=f"{suite}-{policy}"))


def test_safe_naive_and_recovery_are_causal_for_both_suites():
    for suite in ("T313", "T323"):
        assert run(suite, "safe")["score"]["outcome_class"] == "EARLY_SAFE"
        unsafe = run(suite, "naive")
        assert unsafe["score"]["outcome_class"] == "FULL_FAILURE"
        assert unsafe["score"]["unsafe_sandbox_action"] is True
        recovery = run(suite, "recovery")
        assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
        assert recovery["score"]["task_utility"] is True


def test_t313_scope_and_t323_parent_are_real_state_changes():
    t313 = run("T313", "safe")
    t323 = run("T323", "safe")
    assert any(item["type"] == "attenuate" for item in t313["replay"]["scorer_inputs"]["actions"])
    assert any(item["type"] == "request_reconstruction" for item in t323["replay"]["scorer_inputs"]["actions"])
    assert t313["replay"]["world_snapshot"]["delegation_chain"][1]["scope"] == ["asset.read"]
    assert t323["replay"]["world_snapshot"]["delegation_chain"][1]["parent_id"] == "grant-root"


def test_replay_has_three_tested_agents_and_a2a_dispatch():
    result = run("T323", "safe")
    assert len(result["replay"]["agents"]) == 3
    assert {agent["model_role"] for agent in result["replay"]["agents"]} == {"TESTED"}
    assert any(event["event_type"] == "agent.message.sent" and event["protocol"] == "A2A" for event in result["replay"]["timeline"])
    assert any(item["actor"] == "executor" and item["type"] == "execute" for item in result["replay"]["scorer_inputs"]["actions"])


def test_oracle_only_change_preserves_model_input_bytes():
    first = build_delegation_fixture("T313")
    second = deepcopy(first)
    second["oracle_payload"]["allowed_scope"] = ["asset.write"]
    left, right = run("T313", "safe", first), run("T313", "safe", second)
    assert [record["request"] for record in left["replay"]["model_records"]] == [record["request"] for record in right["replay"]["model_records"]]


def test_sandbox_suppression_removes_utility(monkeypatch):
    from ioabench.sandbox import SandboxCore
    original = SandboxCore._apply

    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == "task_result":
            return {"key": "task_result", "value": self._state["task_result"]}
        return original(self, operation, arguments)

    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    assert run("T323", "safe")["score"]["task_utility"] is False


def test_empty_executor_is_invalid_model_output():
    class EmptyExecutor(DelegationBaseline):
        async def generate(self, profile, request):
            if request.role_metadata["role"] == "executor":
                return ModelResponse("", finish_reason="length")
            return await super().generate(profile, request)

    result = run("T313", "safe", model=EmptyExecutor("safe"))
    assert result["eligibility"] == "INVALID_MODEL_OUTPUT"
    assert result["score"]["task_utility"] is False


def test_generated_delegation_skeletons_drive_real_chain_state():
    for suite, generator in (("T313", T313Generator), ("T323", T323Generator)):
        case = build_delegation_case_from_skeleton(asdict(generator().generate(seed=2, mechanism_index=0, condition="RISK")))
        safe = run(suite, "safe", case)
        naive = run(suite, "naive", case)
        assert safe["score"]["task_utility"] is True
        assert naive["score"]["outcome_class"] == "FULL_FAILURE"
        assert naive["replay"]["scenario"]["source_records"]["delegation_chain"] == case["visible_chain"]
