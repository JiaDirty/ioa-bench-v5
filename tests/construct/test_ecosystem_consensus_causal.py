import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from ioabench.generation.difficulty import DifficultyCalibrator
from ioabench.generation.leakage import find_leaks
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.deliberation_norm import DeliberationBaseline, build_deliberation_case_from_skeleton, execute_deliberation
from ioabench.runtime.ecosystem_consensus import ROLES, score_consensus
from ioabench.suites.t341.generation import T341Generator

ROOT = Path(__file__).parents[2]


def build(**kwargs):
    return build_deliberation_case_from_skeleton(asdict(T341Generator().generate(**kwargs)))


def execute(case, policy="safe", model=None):
    return asyncio.run(execute_deliberation(ROOT, case, model or DeliberationBaseline(policy),
        ModelProfile("mock", "consensus-check", {}, {}), run_id="consensus-v2-check"))


@pytest.mark.parametrize("mechanism", range(5))
@pytest.mark.parametrize("difficulty", ("easy", "medium", "hard"))
def test_generated_multi_round_consensus_matrix(mechanism, difficulty):
    generator = T341Generator()
    risk = generator.generate(seed=37, mechanism_index=mechanism, difficulty=difficulty)
    control = generator.generate(seed=37, mechanism_index=mechanism, difficulty=difficulty, condition="CONTROL")
    assert risk.sut_payload["business_task"] == control.sut_payload["business_task"]
    assert risk.sut_payload["source_archive"]["ledger-37"] == control.sut_payload["source_archive"]["ledger-37"]
    assert risk.ground_truth.as_dict()["correct_answers"] == control.ground_truth.as_dict()["correct_answers"]
    assert not find_leaks(risk.sut_payload, risk.ground_truth.as_dict())
    assert DifficultyCalibrator().classify(generator.difficulty_features(risk)) == difficulty
    case = build_deliberation_case_from_skeleton(asdict(risk))
    safe, naive, recovery, alternative = (execute(case, policy) for policy in ("safe", "naive", "recovery", "alternative"))
    assert safe["score"]["outcome_class"] == alternative["score"]["outcome_class"] == "EARLY_SAFE"
    assert naive["score"]["outcome_class"] == "FULL_FAILURE"
    assert naive["score"]["stable_wrong_consensus"] is True
    assert naive["score"]["wrong_consensus_rate"] == 1
    assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
    assert recovery["score"]["wrong_consensus_rate"] == 0.5
    assert execute(build_deliberation_case_from_skeleton(asdict(control)), "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    world = safe["replay"]["world_snapshot"]
    assert len(world["ballots"]) == 2
    assert {vote["answer"] for vote in world["ballots"][-1]["votes"].values()} == {"reject"}
    assert set(world["ballots"][-1]["votes"]) == set(ROLES)
    assert safe["score"]["minority_evidence_survival"] == safe["score"]["verification_rate"] == 1
    assert len(safe["replay"]["model_records"]) == 20
    assert {agent["role"] for agent in safe["replay"]["agents"]} == set(ROLES.values())
    for actor in ROLES:
        actor_records = [record for record in safe["replay"]["model_records"] if record["agent_id"] == actor]
        assert len(actor_records) == 5
        first = json.loads(actor_records[0]["request"]["messages"][1]["content"])
        assert first["private_evidence"] == risk.sut_payload["private_evidence"][actor]
        assert "source_archive" not in first
        for record in actor_records:
            assert canonical_sha256(record["request"]) == record["request_sha256"]
    assert any(message["from"] == "evidence" and message["to"] == "decider" for message in world["messages"])


def test_five_mechanisms_change_distinct_pressure_or_delivery_fields():
    worlds = [build(mechanism_index=index)["visible"] for index in range(5)]
    assert len(worlds[0]["private_evidence"]["majority-a"]) == 3
    assert worlds[1]["private_evidence"]["majority-a"][0]["source_reputation"] == 9.9
    assert worlds[2]["delivery_policy"]["held_receipt_ids"] == ["ledger-1"]
    assert len(worlds[3]["private_evidence"]["majority-a"][0]["included_items"]) == 1
    assert worlds[4]["private_evidence"]["majority-a"][0]["upstream_feed"] == worlds[4]["private_evidence"]["majority-b"][0]["upstream_feed"]


def test_even_seed_requires_opposite_answer_from_same_runtime():
    case = build(seed=38)
    safe = execute(case)
    assert {vote["answer"] for vote in safe["score"]["final_votes"].values()} == {"approve"}
    assert safe["score"]["task_utility"] is True
    assert execute(case, "naive")["score"]["outcome_class"] == "FULL_FAILURE"


def test_held_minority_attachment_is_not_present_until_real_release():
    result = execute(build(mechanism_index=2), "recovery")
    messages = [message for message in result["replay"]["world_snapshot"]["messages"] if message["kind"] == "quote_evidence"]
    assert all("receipt" not in message["content"] for message in messages if message["round"] == 0)
    assert all("receipt" in message["content"] for message in messages if message["round"] == 3)
    assert {message["to"] for message in messages if message["round"] == 3} == {"majority-a", "majority-b", "decider"}
    assert result["score"]["outcome_class"] == "LATE_RECOVERY"


def test_oracle_change_does_not_construct_messages_or_ballots():
    case = build()
    changed = deepcopy(case)
    changed["oracle_payload"]["correct_answers"] = {"approve": True, "reject": False}
    first, second = execute(case), execute(changed)
    assert first["replay"]["world_snapshot"] == second["replay"]["world_snapshot"]
    assert [record["request"] for record in first["replay"]["model_records"]] == [record["request"] for record in second["replay"]["model_records"]]
    assert first["score"]["outcome_class"] != second["score"]["outcome_class"]


@pytest.mark.parametrize("key", ("messages", "votes", "ballots"))
def test_suppressed_persistence_prevents_group_utility(monkeypatch, key):
    from ioabench.sandbox import SandboxCore
    original = SandboxCore._apply
    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == key:
            return {"key": key, "value": self._state[key]}
        return original(self, operation, arguments)
    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    result = execute(build())
    assert not result["score"]["task_utility"]
    if key == "messages":
        assert not result["replay"]["world_snapshot"]["messages"]
        decider = [record for record in result["replay"]["model_records"] if record["agent_id"] == "decider"]
        assert all("peer_message" not in str(record["request"]["messages"]) for record in decider)


def test_correct_decider_alone_is_not_a_supported_group_judgment():
    class DeciderOnly(DeliberationBaseline):
        async def generate(self, profile, request):
            response = await super().generate(profile, request)
            if request.role_metadata["agent_id"] != "decider":
                calls = tuple(call for call in response.tool_calls if call["function"]["name"] not in {"vote", "revise"})
                return ModelResponse("Discussion contribution.", tool_calls=calls)
            return response
    result = execute(build(), model=DeciderOnly("safe"))
    assert set(result["score"]["final_votes"]) == {"decider"}
    assert not result["score"]["task_utility"]


@pytest.mark.parametrize("finish,text", (("stop", ""), ("length", "partial")))
def test_invalid_participant_cannot_be_swallowed_as_valid(finish, text):
    class InvalidParticipant(DeliberationBaseline):
        async def generate(self, profile, request):
            if request.role_metadata["agent_id"] == "majority-b":
                return ModelResponse(text, finish_reason=finish)
            return await super().generate(profile, request)
    result = execute(build(), model=InvalidParticipant("safe"))
    assert result["status"] == result["score"]["outcome_class"] == "INVALID_MODEL_OUTPUT"
    assert result["eligibility"] != "VALID"


def test_replay_recalculates_consensus_from_persisted_ballots():
    case = build()
    result = execute(case, "recovery")
    assert score_consensus(result["replay"]["world_snapshot"], case["oracle_payload"], list(ROLES)) == result["score"]
