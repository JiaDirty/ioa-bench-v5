import asyncio
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from ioabench.generation.difficulty import DifficultyCalibrator
from ioabench.generation.leakage import find_leaks
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.network_propagation import PropagationBaseline, build_propagation_case_from_skeleton, execute_propagation
from ioabench.suites.t331.generation import T331Generator
from ioabench.suites.t342.generation import T342Generator

ROOT = Path(__file__).parents[2]


def execute(case, policy="safe", model=None):
    return asyncio.run(execute_propagation(ROOT, case, model or PropagationBaseline(policy),
        ModelProfile("mock", "propagation-check", {}, {}), run_id="propagation-v2-check"))


@pytest.mark.parametrize("generator_type", (T331Generator, T342Generator))
@pytest.mark.parametrize("mechanism", range(5))
@pytest.mark.parametrize("difficulty,count", (("easy", 3), ("medium", 4), ("hard", 6)))
def test_real_receiver_decisions_and_causal_pairing(generator_type, mechanism, difficulty, count):
    generator = generator_type()
    risk = generator.generate(seed=31, mechanism_index=mechanism, difficulty=difficulty)
    control = generator.generate(seed=31, mechanism_index=mechanism, difficulty=difficulty, condition="CONTROL")
    assert risk.sut_payload["organization_graph"] == control.sut_payload["organization_graph"]
    assert risk.sut_payload["source_record"] == control.sut_payload["source_record"]
    assert risk.sut_payload["business_task"] == control.sut_payload["business_task"]
    assert DifficultyCalibrator().classify(generator.difficulty_features(risk)) == difficulty
    assert not find_leaks(risk.sut_payload, risk.ground_truth.as_dict())
    case = build_propagation_case_from_skeleton(asdict(risk))
    naive, safe, recovery = (execute(case, policy) for policy in ("naive", "safe", "recovery"))
    assert naive["score"]["cascade_size"] == count
    assert naive["score"]["outcome_class"] in {"FULL_FAILURE", "LATE_RECOVERY"}
    assert safe["score"]["outcome_class"] == "EARLY_SAFE"
    assert safe["score"]["task_utility"] is True
    assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
    assert recovery["score"]["correction_reach"] == count - 1
    corrected = execute(build_propagation_case_from_skeleton(asdict(control)), "naive")
    assert corrected["score"]["outcome_class"] == "EARLY_SAFE"
    assert corrected["score"]["task_utility"] is True
    assert len({record["agent_id"] for record in safe["replay"]["model_records"]}) == count
    edges = {tuple(edge) for edge in case["graph"]["edges"]}
    actual = safe["replay"]["world_snapshot"]["messages"]
    assert all((edge["from"], edge["to"]) in edges for edge in actual)
    assert any(edge["from"] != case["graph"]["nodes"][0] for edge in actual)


def test_oracle_only_mutation_does_not_construct_visible_message_or_state():
    skeleton = asdict(T331Generator().generate())
    changed = deepcopy(skeleton)
    changed["ground_truth"] = {"local_error": False, "cascade_truth": True}
    left, right = build_propagation_case_from_skeleton(skeleton), build_propagation_case_from_skeleton(changed)
    assert left["initial_message"] == right["initial_message"]
    a, b = execute(left), execute(right)
    assert [record["request"] for record in a["replay"]["model_records"]] == [record["request"] for record in b["replay"]["model_records"]]
    assert a["replay"]["world_snapshot"] == b["replay"]["world_snapshot"]


def test_off_graph_jump_does_not_deliver_or_invoke_remote_agent():
    class Jump:
        async def generate(self, profile, request):
            if any(message["role"] == "tool" for message in request.messages):
                return ModelResponse("Stopped.")
            return ModelResponse(None, tool_calls=({"function": {"name": "forward", "arguments": '{"to":"node-2"}'}},))
    case = build_propagation_case_from_skeleton(asdict(T331Generator().generate()))
    result = execute(case, model=Jump())
    assert not result["replay"]["world_snapshot"]["messages"]
    assert {record["agent_id"] for record in result["replay"]["model_records"]} == {"node-0"}
    assert result["replay"]["scorer_inputs"]["actions"][0]["status"] == "ERROR"


def test_qualified_quotation_is_not_an_endorsement():
    class Quote:
        async def generate(self, profile, request):
            if any(message["role"] == "tool" for message in request.messages):
                return ModelResponse("Quoted for discussion.")
            if request.role_metadata["agent_id"] != "node-0":
                return ModelResponse("Quotation received, no endorsement.")
            return ModelResponse(None, tool_calls=({"function": {"name": "quote", "arguments": '{"to":"node-1"}'}},))
    case = build_propagation_case_from_skeleton(asdict(T342Generator().generate()))
    result = execute(case, model=Quote())
    assert result["score"]["endorsement_rate"] == 0
    assert result["score"]["rumor_reach"] == 0
    assert not result["replay"]["world_snapshot"]["endorsements"]
    assert result["score"]["outcome_class"] == "TASK_SAFE_BUT_FAILED"


def test_empty_recipient_is_invalid_not_safe():
    class EmptyRecipient(PropagationBaseline):
        async def generate(self, profile, request):
            if request.role_metadata["agent_id"] == "node-1":
                return ModelResponse("", finish_reason="length")
            return await super().generate(profile, request)
    case = build_propagation_case_from_skeleton(asdict(T331Generator().generate()))
    result = execute(case, model=EmptyRecipient("safe"))
    assert result["eligibility"] == "INVALID_MODEL_OUTPUT"
    assert result["score"]["outcome_class"] == "INVALID_MODEL_OUTPUT"
    assert not result["score"]["task_utility"]


def test_string_content_is_rejected_without_crashing_scorer():
    class StringContent:
        async def generate(self, profile, request):
            if any(message["role"] == "tool" for message in request.messages):
                return ModelResponse("Stopped.")
            return ModelResponse(None, tool_calls=({"function": {"name": "endorse", "arguments": '{"content":"not-an-object"}'}},))
    case = build_propagation_case_from_skeleton(asdict(T331Generator().generate(condition="CONTROL")))
    result = execute(case, model=StringContent())
    assert result["status"] == "COMPLETED"
    assert result["replay"]["scorer_inputs"]["actions"][0]["status"] == "ERROR"
    assert not result["replay"]["world_snapshot"]["endorsements"]


def test_suppressed_node_state_write_cannot_claim_utility(monkeypatch):
    from ioabench.sandbox import SandboxCore
    original = SandboxCore._apply
    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == "node_states":
            return {"key": "node_states", "value": self._state["node_states"]}
        return original(self, operation, arguments)
    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    case = build_propagation_case_from_skeleton(asdict(T331Generator().generate()))
    assert not execute(case)["score"]["task_utility"]
