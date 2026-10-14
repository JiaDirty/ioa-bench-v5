"""Reconstruct T311 from ordered actions, request snapshots, and evaluator truth."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256
from ioabench.suites.t311.construct_scoring import score_t311


def audit_t311_replay(replay: Mapping[str, Any], oracle: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    body = {key: value for key, value in replay.items() if key != "content_sha256"}
    if replay.get("content_sha256") != canonical_sha256(body):
        failures.append("bundle hash mismatch")
    scenario = replay.get("scenario", {})
    if scenario.get("test_id") != "T311" or scenario.get("construct_contract_version") != "1.0.0":
        failures.append("construct scenario version mismatch")
    events = replay.get("timeline", [])
    agents = {agent["agent_id"]: agent for agent in replay.get("agents", [])}
    model_records = replay.get("model_records", [])
    for index, record in enumerate(model_records):
        request = record["request"]
        if canonical_sha256(request) != record.get("request_sha256"):
            failures.append(f"request snapshot hash mismatch: {index}")
        matching = [event for event in events if event["event_type"] == "model.input" and
                    event.get("attributes", {}).get("model_record_index") == index]
        if len(matching) != 1 or matching[0].get("payload_sha256") != canonical_sha256(request):
            failures.append(f"model input chronology mismatch: {index}")
        actor = record["agent_id"]
        if actor not in agents or request["role_metadata"]["agent_id"] != actor:
            failures.append(f"actor isolation mismatch: {index}")
        elif any(item["function"]["name"] not in agents[actor]["tools"] for item in request["tools"]):
            failures.append(f"tool permissions mismatch: {index}")
        if any("oracle_payload" in str(message) for message in request["messages"]):
            failures.append(f"Oracle in model input: {index}")
        if index + 1 < len(model_records):
            current = request["messages"]
            actor_records = [other for other in model_records[index + 1:] if other["agent_id"] == actor]
            if actor_records and len(current) > len(actor_records[0]["request"]["messages"]):
                failures.append(f"future message in earlier request: {index}")
    actions = replay.get("scorer_inputs", {}).get("actions", [])
    action_events = [event for event in events if event["event_type"] == "construct.action"]
    if len(action_events) != len(actions):
        failures.append("action timeline count mismatch")
    state = deepcopy(scenario.get("initial_world", {}))
    for index, action in enumerate(actions):
        if index < len(action_events) and (action_events[index].get("attributes", {}).get("action_id") != action.get("action_id")
                                           or action_events[index].get("payload_sha256") != canonical_sha256(action)):
            failures.append(f"action timeline hash mismatch: {index}")
        if action.get("before") != state or not action.get("action_id") == f"action-{index + 1}":
            failures.append(f"action pre-state mismatch: {index}")
        state = deepcopy(action.get("after", {}))
        if action.get("type") == "execute_business_action" and action.get("status") == "OK":
            additions = state.get("access_log", [])[len(action.get("before", {}).get("access_log", [])):]
            if len(additions) != 1 or additions[0].get("agent_id") != action.get("actor"):
                failures.append(f"business action lacks actual state transition: {index}")
    if state != replay.get("world_snapshot"):
        failures.append("world snapshot not reproducible from action chain")
    if scenario.get("manifest", {}).get("action_budget") != scenario.get("budgets"):
        failures.append("manifest/scenario budget mismatch")
    if scenario.get("manifest", {}).get("scenario_sha256") != canonical_sha256({
            "task": scenario.get("task"), "registry_cards": scenario.get("registry_cards"), "source_records": scenario.get("source_records")}):
        failures.append("scenario hash mismatch")
    if not failures:
        score = score_t311(actions, state, oracle, scenario["task"])
        if score != replay.get("scorer_inputs", {}).get("score") or score["task_utility"] != replay.get("final_utility", {}).get("task_success"):
            failures.append("scorer/utility reconstruction mismatch")
    return {"status": "PASS" if not failures else "FAIL", "failures": failures, "model_calls": len(model_records), "actions": len(actions)}
