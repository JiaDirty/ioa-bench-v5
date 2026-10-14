import asyncio
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from ioabench.generation.difficulty import DifficultyCalibrator
from ioabench.generation.leakage import find_leaks
from ioabench.models import ModelProfile
from ioabench.runtime.protocol_state_machine import ProtocolBaseline, build_protocol_case_from_skeleton, execute_protocol
from ioabench.suites.t322.generation import T322Generator

ROOT = Path(__file__).parents[2]


def execute(case, policy="safe"):
    return asyncio.run(execute_protocol(ROOT, case, ProtocolBaseline(policy),
        ModelProfile("mock", "interop-check", {}, {}), run_id="interop-v2-check"))


@pytest.mark.parametrize("mechanism", range(5))
@pytest.mark.parametrize("difficulty", ("easy", "medium", "hard"))
def test_mapping_intervention_changes_real_effects_and_recovery(mechanism, difficulty):
    generator = T322Generator()
    risk = generator.generate(seed=29, mechanism_index=mechanism, difficulty=difficulty)
    control = generator.generate(seed=29, mechanism_index=mechanism, difficulty=difficulty, condition="CONTROL")
    assert risk.sut_payload["initial_ledger"] == control.sut_payload["initial_ledger"]
    assert risk.sut_payload["target_receipt"] == control.sut_payload["target_receipt"]
    assert risk.sut_payload["business_task"] == control.sut_payload["business_task"]
    assert not find_leaks(risk.sut_payload, risk.ground_truth.as_dict())
    assert not find_leaks(control.sut_payload, control.ground_truth.as_dict())
    assert DifficultyCalibrator().classify(generator.difficulty_features(risk)) == difficulty
    case = build_protocol_case_from_skeleton(asdict(risk))
    naive, safe, recovery = (execute(case, policy) for policy in ("naive", "safe", "recovery"))
    assert naive["score"]["outcome_class"] == "FULL_FAILURE"
    assert len([effect for effect in naive["replay"]["world_snapshot"]["ledger"] if not effect["reversed"]]) == 2
    assert safe["score"]["task_utility"] is True
    assert safe["score"]["duplicate_side_effect_rate"] == 0
    assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
    assert recovery["score"]["task_utility"] is True
    assert len([effect for effect in recovery["replay"]["world_snapshot"]["ledger"] if not effect["reversed"]]) == 1
    assert any(effect["reversed"] for effect in recovery["replay"]["world_snapshot"]["ledger"])
    assert execute(build_protocol_case_from_skeleton(asdict(control)), "naive")["score"]["task_utility"] is True
    assert {record["agent_id"] for record in safe["replay"]["model_records"]} == {"source", "destination"}


def test_five_mechanisms_change_distinct_mapping_rules():
    keys = ("status_map", "cancellation_scope", "ttl_scale", "error_map", "forward_idempotency_key")
    for mechanism, key in enumerate(keys):
        generator = T322Generator()
        risk = generator.generate(mechanism_index=mechanism).sut_payload["gateway_mapping"]
        control = generator.generate(mechanism_index=mechanism, condition="CONTROL").sut_payload["gateway_mapping"]
        assert {name for name in risk if risk[name] != control[name]} == {key}


def test_oracle_only_mutation_preserves_input_and_ledger():
    skeleton = asdict(T322Generator().generate(mechanism_index=4))
    changed = deepcopy(skeleton)
    changed["ground_truth"] = {"semantic_mapping_valid": True, "duplicate_side_effect": False}
    left, right = execute(build_protocol_case_from_skeleton(skeleton)), execute(build_protocol_case_from_skeleton(changed))
    assert [record["request"] for record in left["replay"]["model_records"]] == [record["request"] for record in right["replay"]["model_records"]]
    assert left["replay"]["world_snapshot"] == right["replay"]["world_snapshot"]


def test_suppressed_compensation_cannot_claim_recovery(monkeypatch):
    from ioabench.sandbox import SandboxCore
    original = SandboxCore._apply
    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == "ledger" and any(item["reversed"] for item in arguments["value"]):
            return {"key": "ledger", "value": self._state["ledger"]}
        return original(self, operation, arguments)
    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    case = build_protocol_case_from_skeleton(asdict(T322Generator().generate()))
    result = execute(case, "recovery")
    assert result["score"]["outcome_class"] == "FULL_FAILURE"
    assert not result["score"]["task_utility"]
    assert result["score"]["recovery_rate"] == 0
