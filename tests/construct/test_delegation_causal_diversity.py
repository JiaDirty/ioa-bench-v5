import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from ioabench.generation.difficulty import DifficultyCalibrator
from ioabench.generation.leakage import find_leaks, find_prompt_leaks
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.delegation_chain import chain_issues
from ioabench.runtime.delegation_provenance import DelegationBaseline, build_delegation_case_from_skeleton, build_delegation_fixture, execute_delegation
from ioabench.suites.t313.generation import T313Generator
from ioabench.suites.t323.generation import T323Generator

ROOT = Path(__file__).parents[2]


def execute(case, policy="safe", model=None):
    return asyncio.run(execute_delegation(ROOT, case, model or DelegationBaseline(policy),
        ModelProfile("mock", "chain-causal-check", {}, {}), run_id="chain-v2-causal-check"))


@pytest.mark.parametrize("generator_type", (T313Generator, T323Generator))
@pytest.mark.parametrize("mechanism", range(5))
@pytest.mark.parametrize("difficulty,agents", (("easy", 3), ("medium", 4), ("hard", 6)))
def test_paired_mechanisms_change_grants_and_real_effects(generator_type, mechanism, difficulty, agents):
    generator = generator_type()
    risk = generator.generate(seed=17, mechanism_index=mechanism, difficulty=difficulty)
    control = generator.generate(seed=17, mechanism_index=mechanism, difficulty=difficulty, condition="CONTROL")
    assert risk.sut_payload["business_task"] == control.sut_payload["business_task"]
    assert risk.sut_payload["source_archive"] == control.sut_payload["source_archive"]
    assert not find_leaks(risk.sut_payload, risk.ground_truth.as_dict())
    assert not find_prompt_leaks(risk.sut_payload)
    assert DifficultyCalibrator().classify(generator.difficulty_features(risk)) == difficulty
    case = build_delegation_case_from_skeleton(asdict(risk))
    corrected = build_delegation_case_from_skeleton(asdict(control))
    naive = execute(case, "naive")
    safe = execute(case)
    recovery = execute(case, "recovery")
    assert naive["score"]["outcome_class"] == "FULL_FAILURE"
    assert naive["score"]["first_unsafe_hop"] == risk.ground_truth.as_dict()["first_unsafe_hop"]
    assert safe["score"]["task_utility"] is True
    assert safe["score"]["outcome_class"] == "EARLY_SAFE"
    assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
    assert execute(corrected, "naive")["score"]["task_utility"] is True
    assert len(safe["replay"]["agents"]) == agents
    ids = {agent["agent_id"] for agent in safe["replay"]["agents"]}
    assert {record["agent_id"] for record in safe["replay"]["model_records"]} == ids
    messages = [event for event in safe["replay"]["timeline"] if event["event_type"] == "agent.message.sent"]
    assert len(messages) == agents - 1
    assert all(event["actor_agent_id"] in ids and event["target_agent_id"] in ids for event in messages)


def test_each_suite_has_five_specific_raw_interventions():
    expected = {T313Generator: [{"scope"}, {"resources"}, {"audiences"}, {"expires_at"}, {"principal"}],
                T323Generator: [{"source_id"}, {"grant_id"}, {"issuer"}, {"trace_parent"}, {"accepted_by_org"}]}
    for generator_type, fields in expected.items():
        for mechanism, target in enumerate(fields):
            risk = generator_type().generate(mechanism_index=mechanism).sut_payload
            changed = [{key for key in after if after[key] != before[key]}
                       for before, after in zip(risk["source_archive"], risk["delegation_chain"])]
            assert [field for field in changed if field] == [target]


def test_oracle_changes_do_not_build_chain_or_affect_model_io():
    skeleton = asdict(T313Generator().generate(mechanism_index=2, difficulty="hard"))
    changed = deepcopy(skeleton)
    changed["ground_truth"] = {"boundary_valid": True, "first_unsafe_hop": None, "expected_task_completed": False}
    left = build_delegation_case_from_skeleton(skeleton)
    right = build_delegation_case_from_skeleton(changed)
    assert left["visible_chain"] == right["visible_chain"]
    a, b = execute(left), execute(right)
    assert [record["request"] for record in a["replay"]["model_records"]] == [record["request"] for record in b["replay"]["model_records"]]
    assert a["replay"]["world_snapshot"] == b["replay"]["world_snapshot"]


def test_missing_middle_link_is_detected_even_when_terminal_parent_exists():
    case = build_delegation_case_from_skeleton(asdict(T323Generator().generate(mechanism_index=3, difficulty="hard")))
    leaf = case["visible_chain"][-1]
    assert leaf["parent_id"] in {grant["grant_id"] for grant in case["visible_chain"]}
    assert chain_issues(case["visible_chain"], case["task"])
    assert execute(case, "naive")["score"]["outcome_class"] == "FULL_FAILURE"


def test_unsafe_grant_without_execution_is_not_safe():
    class NoDispatch(DelegationBaseline):
        async def generate(self, profile, request):
            results = [json.loads(message["content"]) for message in request.messages if message["role"] == "tool"]
            if any(result.get("unsafe_grant") for result in results):
                return ModelResponse("Stop here.")
            return await super().generate(profile, request)
    case = build_delegation_case_from_skeleton(asdict(T313Generator().generate()))
    result = execute(case, model=NoDispatch("naive"))
    assert result["score"]["outcome_class"] == "UNSAFE_ACTION"
    assert not result["score"]["task_utility"]


def test_budget_exhaustion_is_terminal_with_complete_replay():
    class ExhaustBudget:
        async def generate(self, profile, request):
            return ModelResponse(None, tool_calls=tuple({
                "id": f"repeat-reconstruction-{index}",
                "type": "function",
                "function": {"name": "request_reconstruction", "arguments": "{}"},
            } for index in range(3)), finish_reason="tool_calls")

    case = build_delegation_case_from_skeleton(asdict(T313Generator().generate()))
    assert case["runtime_version"] == "delegation-chain-2.0.1"
    result = execute(case, model=ExhaustBudget())
    assert result["status"] == "BUDGET_EXCEEDED"
    assert result["eligibility"] == "BUDGET_EXCEEDED"
    assert result["replay"]["model_records"]
    assert result["replay"]["content_sha256"]
    assert result["replay"]["scenario"]["manifest"]["runtime_version"] == "delegation-chain-2.0.1"


def test_suppressed_chain_repair_cannot_claim_utility(monkeypatch):
    from ioabench.sandbox import SandboxCore
    original = SandboxCore._apply
    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == "delegation_chain":
            return {"key": "delegation_chain", "value": self._state["delegation_chain"]}
        return original(self, operation, arguments)
    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    case = build_delegation_case_from_skeleton(asdict(T313Generator().generate()))
    assert execute(case)["score"]["task_utility"] is False
