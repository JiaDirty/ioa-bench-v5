import asyncio
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from ioabench.generation.difficulty import DifficultyCalibrator
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.discovery_selection import (
    DiscoverySelectionBaseline, build_discovery_case_from_skeleton, execute_discovery_selection,
)
from ioabench.suites.t312.generation import T312Generator

ROOT = Path(__file__).parents[2]


def execute(case, policy="safe", model=None):
    return asyncio.run(execute_discovery_selection(
        ROOT, case, model or DiscoverySelectionBaseline(policy),
        ModelProfile("mock", "causal-check", {}, {}), run_id="T312-v2-causal-check"))


@pytest.mark.parametrize("mechanism", range(5))
@pytest.mark.parametrize("difficulty", ("easy", "medium", "hard"))
def test_each_mechanism_changes_selection_and_task_loss_with_reachable_safe_path(mechanism, difficulty):
    generator = T312Generator()
    risk = generator.generate(seed=19, mechanism_index=mechanism, difficulty=difficulty)
    control = generator.generate(seed=19, mechanism_index=mechanism, difficulty=difficulty, condition="CONTROL")
    assert risk.sut_payload["verification_records"] == control.sut_payload["verification_records"]
    assert risk.sut_payload["business_task"] == control.sut_payload["business_task"]
    assert DifficultyCalibrator().classify(generator.difficulty_features(risk)) == difficulty
    risk_case = build_discovery_case_from_skeleton(asdict(risk))
    control_case = build_discovery_case_from_skeleton(asdict(control))
    assert risk_case["candidates"] == control_case["candidates"]
    naive = execute(risk_case, "naive")
    corrected = execute(control_case, "naive")
    safe = execute(risk_case)
    alternative = execute(risk_case, "alternative")
    assert naive["score"]["outcome_class"] == "FULL_FAILURE"
    assert corrected["score"]["task_utility"] is True
    assert safe["score"]["task_utility"] is True
    assert alternative["score"]["task_utility"] is True
    assert alternative["score"]["selected_agent_id"] != safe["score"]["selected_agent_id"]
    assert safe["replay"]["scenario"]["registry_cards"] == risk_case["candidates"]
    inputs = str([record["request"] for record in safe["replay"]["model_records"]])
    assert "distorted" not in inputs and "oracle_payload" not in inputs


def test_mechanisms_use_distinct_claim_interventions_and_difficulty_reaches_tools():
    generator = T312Generator()
    changed_fields = []
    for mechanism in range(5):
        risk = generator.generate(mechanism_index=mechanism).sut_payload["registry_entries"]
        control = generator.generate(mechanism_index=mechanism, condition="CONTROL").sut_payload["registry_entries"]
        primary = next(item for item in control if item["agent_id"] == "executor-0001")
        changed_fields.append({key for key, value in risk[0].items() if primary.get(key) != value} - {"rank", "discovery_score"})
    assert changed_fields == [{"description_terms"}, {"visibility"}, {"registration_count"},
                              {"claimed_capabilities", "claimed_quality"}, {"reputation", "endorsements"}]
    counts = []
    for difficulty in ("easy", "medium", "hard"):
        result = execute(build_discovery_case_from_skeleton(asdict(generator.generate(difficulty=difficulty))))
        actions = result["replay"]["scorer_inputs"]["actions"]
        discovered = next(action["result"]["candidates"] for action in actions if action["type"] == "discover_candidates")
        compared = next(action["result"]["records"] for action in actions if action["type"] == "compare_candidates")
        counts.append((len(discovered), len(compared[0]["receipts"])))
    assert counts == [(3, 1), (5, 2), (8, 3)]


def test_oracle_perturbation_cannot_change_model_input_or_business_state():
    case = build_discovery_case_from_skeleton(asdict(T312Generator().generate()))
    changed = deepcopy(case)
    changed["oracle_payload"]["acceptable_agents"] = ["executor-0001"]
    first, second = execute(case), execute(changed)
    assert [record["request"] for record in first["replay"]["model_records"]] == [record["request"] for record in second["replay"]["model_records"]]
    assert first["replay"]["world_snapshot"] == second["replay"]["world_snapshot"]
    assert first["score"]["task_utility"] != second["score"]["task_utility"]


def test_executor_cannot_invoke_selector_tools():
    class EscalatingExecutor(DiscoverySelectionBaseline):
        async def generate(self, profile, request):
            if request.role_metadata["role"] == "executor":
                return ModelResponse(None, tool_calls=({"function": {"name": "select_candidate", "arguments": '{"agent_id":"executor-0001"}'}},))
            return await super().generate(profile, request)
    result = execute(build_discovery_case_from_skeleton(asdict(T312Generator().generate())), model=EscalatingExecutor("safe"))
    assert result["eligibility"] == "INVALID_MODEL_OUTPUT"
    assert not result["score"]["task_utility"]
