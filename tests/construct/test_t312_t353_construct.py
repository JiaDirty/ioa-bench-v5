import asyncio
from copy import deepcopy
from pathlib import Path

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelResponse
from ioabench.replay.construct_audit import audit_t311_replay
from ioabench.runtime.discovery_selection import DiscoverySelectionBaseline, build_discovery_fixture, execute_discovery_selection, run_discovery_baseline
from ioabench.runtime.discovery_selection import build_discovery_case_from_skeleton
from dataclasses import asdict
from ioabench.suites.t312.generation import T312Generator
from ioabench.suites.t353.generation import T353Generator

ROOT = Path(__file__).parents[2]


def run(suite, policy, case=None, model=None):
    case = case or build_discovery_fixture(suite)
    return asyncio.run(execute_discovery_selection(ROOT, case, model or DiscoverySelectionBaseline(policy), ModelProfile("mock", "offline-selection", {"tools": True}, {}), run_id=f"{suite}-{policy}"))


def test_both_suites_have_real_selection_and_business_state_outcomes():
    for suite in ("T312", "T353"):
        assert run(suite, "safe")["score"]["outcome_class"] == "EARLY_SAFE"
        unsafe = run(suite, "naive")
        assert unsafe["score"]["outcome_class"] == "FULL_FAILURE"
        assert unsafe["score"]["unsafe_sandbox_action"] is True
        assert unsafe["replay"]["world_snapshot"]["task_result"]["unsafe_effect"] is True


def test_alternative_and_recovery_are_distinct_valid_paths():
    for suite in ("T312", "T353"):
        assert run(suite, "alternative")["score"]["task_utility"] is True
        recovery = run(suite, "recovery")
        assert recovery["score"]["outcome_class"] == "LATE_RECOVERY"
        assert recovery["score"]["selection_count"] == 2


def test_rank_and_raw_evidence_change_visible_selection_without_oracle_change():
    case = build_discovery_fixture("T312")
    changed = deepcopy(case)
    changed["visible_directory"]["ranking_mode"] = "honest"
    first = run("T312", "naive", case)
    second = run("T312", "naive", changed)
    assert first["score"]["selected_agent_id"] == "distorted-agent"
    assert second["score"]["selected_agent_id"] == "alternative-agent"
    assert case["oracle_payload"] == changed["oracle_payload"]
    assert first["replay"]["scenario"]["manifest"]["dataset_sha256"] != second["replay"]["scenario"]["manifest"]["dataset_sha256"]


def test_oracle_only_change_does_not_change_model_records():
    case = build_discovery_fixture("T353")
    changed = deepcopy(case)
    changed["oracle_payload"]["acceptable_agents"] = ["distorted-agent"]
    first, second = run("T353", "safe", case), run("T353", "safe", changed)
    assert [x["request"] for x in first["replay"]["model_records"]] == [x["request"] for x in second["replay"]["model_records"]]
    assert first["replay"]["scenario"]["source_records"] == second["replay"]["scenario"]["source_records"]
    assert first["score"]["outcome_class"] != second["score"]["outcome_class"]


def test_replay_contains_two_tested_agents_and_explicit_a2a():
    result = run("T312", "safe")
    agents = result["replay"]["agents"]
    assert {agent["model_role"] for agent in agents} == {"TESTED"}
    assert len(agents) == 2
    assert any(event["event_type"] == "agent.message.sent" and event["protocol"] == "A2A" for event in result["replay"]["timeline"])
    assert any(action["type"] == "execute_task" and action["actor"] == "honest-agent" for action in result["replay"]["scorer_inputs"]["actions"])


def test_sandbox_mutation_is_required_for_utility(monkeypatch):
    from ioabench.sandbox import SandboxCore
    original = SandboxCore._apply
    def suppress(self, operation, arguments):
        if operation == "set" and arguments.get("key") == "task_result":
            return {"key": "task_result", "value": self._state["task_result"]}
        return original(self, operation, arguments)
    monkeypatch.setattr(SandboxCore, "_apply", suppress)
    result = run("T353", "safe")
    assert result["score"]["task_utility"] is False


def test_empty_executor_is_invalid_model_output():
    class EmptyExecutor(DiscoverySelectionBaseline):
        async def generate(self, profile, request):
            if request.role_metadata["role"] == "executor":
                return ModelResponse("", finish_reason="length")
            return await super().generate(profile, request)
    result = run("T312", "safe", model=EmptyExecutor("safe"))
    assert result["eligibility"] == "INVALID_MODEL_OUTPUT"
    assert result["score"]["task_utility"] is False


def test_replay_snapshot_is_not_mutable_after_model_call():
    result = run("T353", "safe")
    first = result["replay"]["model_records"][0]["request"]
    assert all(message["role"] != "tool" for message in first["messages"])
    assert canonical_sha256(first) == result["replay"]["model_records"][0]["request_sha256"]


def test_generated_discovery_skeletons_drive_real_selection_and_sandbox():
    for suite, generator in (("T312", T312Generator), ("T353", T353Generator)):
        case = build_discovery_case_from_skeleton(asdict(generator().generate(seed=7, mechanism_index=0, condition="RISK")))
        safe = run(suite, "safe", case)
        naive = run(suite, "naive", case)
        assert safe["score"]["task_utility"] is True
        assert naive["score"]["outcome_class"] == "FULL_FAILURE"
        assert naive["replay"]["scenario"]["registry_cards"] == case["candidates"]
        assert naive["replay"]["scenario"]["task"] == case["task"]
