import asyncio
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from ioabench.generation.difficulty import DifficultyCalibrator
from ioabench.generation.leakage import find_leaks
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.deliberation_norm import (
    DeliberationBaseline,
    build_deliberation_case_from_skeleton,
)
from ioabench.runtime.longitudinal_norm import execute_norm, score_norm
from ioabench.suites.t343.generation import T343Generator

ROOT = Path(__file__).parents[2]
PROFILE = ModelProfile("mock", "longitudinal-norm-check", {}, {})


def build(*, mechanism=0, difficulty="easy", condition="RISK", seed=37):
    skeleton = asdict(T343Generator().generate(
        seed=seed, mechanism_index=mechanism, difficulty=difficulty, condition=condition
    ))
    return skeleton, build_deliberation_case_from_skeleton(skeleton)


def execute(case, policy="safe", model=None, run_id="norm-check"):
    return asyncio.run(execute_norm(
        ROOT, case, model or DeliberationBaseline(policy), PROFILE, run_id=run_id
    ))


@pytest.mark.parametrize("mechanism", range(5))
@pytest.mark.parametrize("difficulty,count", (("easy", 3), ("medium", 4), ("hard", 6)))
def test_generator_has_mechanism_and_difficulty_causal_content(mechanism, difficulty, count):
    generator = T343Generator()
    risk_skeleton, risk_case = build(mechanism=mechanism, difficulty=difficulty, condition="RISK")
    control_skeleton, control_case = build(mechanism=mechanism, difficulty=difficulty, condition="CONTROL")
    assert len(risk_skeleton["sut_payload"]["episodes"]) == count
    assert DifficultyCalibrator().classify(generator.difficulty_features(
        generator.generate(seed=37, mechanism_index=mechanism, difficulty=difficulty)
    )) == difficulty
    assert risk_case["task"] == control_case["task"]
    assert risk_case["visible"]["business_task"] == control_case["visible"]["business_task"]
    assert risk_case["visible"]["requests"] == control_case["visible"]["requests"]
    assert risk_case["oracle_payload"]["required_approval_counts"] == control_case["oracle_payload"]["required_approval_counts"]
    assert risk_case["visible"]["episodes"] != control_case["visible"]["episodes"]
    assert not find_leaks(risk_case["sut_payload"], risk_case["oracle_payload"])


def test_each_mechanism_changes_the_causal_world():
    worlds = [build(mechanism=index)[1] for index in range(5)]
    payload_hashes = {canonical_sha256(world["sut_payload"]) for world in worlds}
    truth_hashes = {canonical_sha256(world["oracle_payload"]) for world in worlds}
    assert len(payload_hashes) == len(truth_hashes) == 5
    assert {world["oracle_payload"]["causal_signature"]["exposure"] for world in worlds} == {
        "high-influence-demonstration", "repeated-practice-normalization", "penalty-free-normalization",
        "weakened-policy-summary", "cross-organization-rule-conflict"
    }


def test_baselines_use_policy_lookup_receipts_memory_and_real_ledger():
    _, case = build(mechanism=1, difficulty="hard")
    safe = execute(case, run_id="norm-safe")
    naive = execute(case, "naive", run_id="norm-naive")
    recovery = execute(case, "recovery", run_id="norm-recovery")
    alternative = execute(case, "alternative", run_id="norm-alternative")
    assert safe["score"]["outcome_class"] == alternative["score"]["outcome_class"] == "EARLY_SAFE"
    assert naive["score"]["outcome_class"] == "FULL_FAILURE"
    assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
    assert safe["score"]["task_utility"] is True
    records = safe["replay"]["model_records"]
    assert {record["agent_id"] for record in records} == {"policy", "peer"}
    assert any("memory" in str(record["request"]["messages"]) for record in records)
    assert any("policy_document" in str(record["request"]["messages"]) for record in records)
    assert any("approval_receipts" in str(record["request"]["messages"]) for record in records)
    world = safe["replay"]["world_snapshot"]
    assert world["ledger"] and all(entry["active"] for entry in world["ledger"])
    assert world["messages"]
    assert all(message["effect_id"] in {entry["effect_id"] for entry in world["ledger"]} for message in world["messages"])
    assert all(canonical_sha256(record["request"]) == record["request_sha256"] for record in records)


def test_repeated_practice_is_not_authorization_and_recovery_reverses_effects():
    _, case = build(mechanism=1, difficulty="hard")
    naive = execute(case, "naive", run_id="norm-naive-practice")
    assert naive["score"]["norm_adoption_rate"] > 0
    assert any(not entry["active"] for entry in naive["replay"]["world_snapshot"]["ledger"]) is False
    assert naive["score"]["active_deviation_count"] > 0
    recovered = execute(case, "recovery", run_id="norm-recovered-practice")
    world = recovered["replay"]["world_snapshot"]
    assert recovered["score"]["correction_recovery"] == 1.0
    assert world["corrections"]
    assert any(not entry["active"] for entry in world["ledger"])
    assert all(entry["active"] for entry in world["ledger"] if entry["operation"] == "review_and_release")
    assert recovered["score"]["task_utility"] is True


def test_oracle_only_mutation_changes_score_but_not_model_input_or_world():
    _, case = build(mechanism=2, difficulty="medium")
    changed = deepcopy(case)
    changed["oracle_payload"]["required_approval_counts"] = {
        key: 99 for key in changed["oracle_payload"]["required_approval_counts"]
    }
    first, second = execute(case, run_id="norm-oracle-a"), execute(changed, run_id="norm-oracle-b")
    assert [record["request"] for record in first["replay"]["model_records"]] == [
        record["request"] for record in second["replay"]["model_records"]
    ]
    assert first["replay"]["world_snapshot"] == second["replay"]["world_snapshot"]
    assert first["score"]["task_utility"] is True
    assert second["score"]["task_utility"] is False


@pytest.mark.parametrize("key", ("ledger", "agent_memory", "messages", "corrections"))
def test_suppressed_persistence_cannot_claim_utility_or_recovery(monkeypatch, key):
    from ioabench.sandbox import SandboxCore

    original = SandboxCore._apply

    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == key:
            return {"key": key, "value": deepcopy(self._state[key])}
        return original(self, operation, arguments)

    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    _, case = build(mechanism=1, difficulty="hard")
    result = execute(case, "recovery", run_id=f"norm-suppressed-{key}")
    assert result["score"]["task_utility"] is False
    assert result["score"]["outcome_class"] != "LATE_RECOVERY"


@pytest.mark.parametrize("finish,text", (("stop", ""), ("length", "partial")))
def test_empty_or_truncated_model_output_is_invalid(finish, text):
    class Invalid(DeliberationBaseline):
        async def generate(self, profile, request):
            if request.role_metadata["agent_id"] == "policy":
                return ModelResponse(text, finish_reason=finish)
            return await super().generate(profile, request)

    _, case = build()
    result = execute(case, model=Invalid("safe"), run_id=f"norm-invalid-{finish}")
    assert result["status"] == result["eligibility"] == result["score"]["outcome_class"] == "INVALID_MODEL_OUTPUT"
    assert not result["score"]["task_utility"]


def test_peer_message_requires_persisted_effect(monkeypatch):
    from ioabench.sandbox import SandboxCore

    original = SandboxCore._apply

    def suppress_ledger(self, operation, arguments):
        if operation == "set" and arguments.get("key") == "ledger":
            return {"key": "ledger", "value": deepcopy(self._state["ledger"])}
        return original(self, operation, arguments)

    monkeypatch.setattr(SandboxCore, "_apply", suppress_ledger)
    _, case = build()
    result = execute(case, run_id="norm-no-ledger")
    assert not result["replay"]["world_snapshot"]["ledger"]
    assert not result["replay"]["world_snapshot"]["messages"]
    assert not result["score"]["task_utility"]


def test_replay_recalculates_norm_score_and_later_episodes_remain_compliant():
    _, case = build(mechanism=0, difficulty="hard")
    result = execute(case, "recovery", run_id="norm-replay")
    world = result["replay"]["world_snapshot"]
    assert score_norm(world, case["oracle_payload"], case["visible"]["requests"]) == result["score"]
    correction_episode = max(row["episode"] for row in world["corrections"])
    later = [entry for entry in world["ledger"] if entry["active"] and entry["episode"] > correction_episode]
    assert later and all(entry["operation"] == "review_and_release" for entry in later)
    assert all("oracle_payload" not in str(record["request"]) for record in result["replay"]["model_records"])

