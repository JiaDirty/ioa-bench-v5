"""Tool results are observations at execution time, not live aliases of world state."""
import asyncio
from copy import deepcopy
import json

from ioabench.models import ModelProfile
from ioabench.v5.core.engine import ActionRecord, run_episode
from ioabench.v5.core.trace_integrity import inspect_tool_observations
from ioabench.v5.dynamic import t352_slice


def test_action_record_snapshots_nested_inputs_and_exports():
    arguments = {"selection": ["first"]}
    result = {"history": [{"value": "original"}]}
    action = ActionRecord(1, 1, "worker", "read", arguments, "ok", result)
    arguments["selection"].append("later")
    result["history"][0]["value"] = "later"
    result["history"].append({"value": "new"})
    assert action.arguments == {"selection": ["first"]}
    assert action.result == {"history": [{"value": "original"}]}
    exported = action.as_dict()
    exported["result"]["history"].clear()
    assert action.result == {"history": [{"value": "original"}]}


def test_t352_later_rounds_do_not_rewrite_prior_tool_observations():
    profile = ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY")
    for case in t352_slice.generate(20261020, families=1)[0]:
        for name, model in t352_slice.policies().items():
            trace = asyncio.run(run_episode(case, t352_slice.T352DynamicScenario(), model,
                                           profile, parameters={"temperature": 0.0}))
            assert trace.status == "COMPLETED"
            assert trace.final_state["reports_seen"]
            initial = next(action for action in trace.actions if action.tool == "read_history")
            assert initial.result["current_round"] == 1
            assert initial.result["delivery_history"] == []
            for action in trace.actions_of("read_history"):
                assert all(report["round"] < action.result["current_round"]
                           for report in action.result["delivery_history"])
            visible_initial = next(json.loads(message["content"])
                for record in trace.records for message in record["request"]["messages"]
                if message.get("role") == "tool" and "delivery_history" in message.get("content", ""))
            assert initial.result == visible_initial
            assert t352_slice.score(trace, case).safety == t352_slice.EXPECTED_REFERENCE[name][case.arm]
            check = inspect_tool_observations({"actions": [a.as_dict() for a in trace.actions],
                                               "records": trace.records})
            assert check["compared"] > 0
            assert not check["mismatches"] and not check["alignment_errors"]


def _repeated_id_trace():
    tool_call = {"id": "reused", "function": {"name": "read", "arguments": "{}"}}
    messages = []
    records = []
    for value in (1, 2):
        records.append({"agent_id": "worker", "turn": 1,
                        "request": {"messages": deepcopy(messages)},
                        "response": {"tool_calls": [tool_call]}})
        messages.extend([{"role": "assistant", "tool_calls": [tool_call]},
                         {"role": "tool", "tool_call_id": "reused", "content": json.dumps({"value": value})}])
    records.append({"agent_id": "worker", "turn": 1, "request": {"messages": messages},
                    "response": {"tool_calls": []}})
    return {"actions": [ActionRecord(i, 1, "worker", "read", {}, "ok", {"value": i}).as_dict()
                        for i in (1, 2)], "records": records}


def test_observation_integrity_matches_reused_ids_by_execution_position():
    trace = _repeated_id_trace()
    assert inspect_tool_observations(trace)["compared"] == 2
    trace["actions"][1]["result"]["value"] = 3
    result = inspect_tool_observations(trace)
    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["action_index"] == 1
    assert result["mismatches"][0]["observed_tool_pointer"] == "/records/2/request/messages/3/content"
    assert not result["alignment_errors"]


def test_observation_integrity_reports_unobserved_terminal_and_bad_alignment():
    trace = _repeated_id_trace()
    trace["records"].pop()
    result = inspect_tool_observations(trace)
    assert result["compared"] == 1
    assert result["not_observed_in_a_later_request"] == 1
    assert not result["mismatches"] and not result["alignment_errors"]
    trace["records"][1]["request"]["messages"][1]["tool_call_id"] = "wrong"
    assert inspect_tool_observations(trace)["alignment_errors"]
