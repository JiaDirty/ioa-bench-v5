"""Cross-check persisted action results against the tool bytes actually seen by the SUT."""
from __future__ import annotations

import json

from ioabench.hashing import canonical_sha256


def inspect_tool_observations(trace):
    """Match calls in execution order; repeated call IDs cannot merge observations.

    A tool response is directly witnessed by the next retained request for its actor.
    A terminal response without a later request is unobserved, never inferred correct.
    This checks retained bytes only and does not rerun tools, models or scoring.
    """
    actions, records = trace["actions"], trace["records"]
    compared, unavailable, findings, alignment_errors = 0, 0, [], []
    action_index = 0
    for record_index, record in enumerate(records):
        later_index = next((i for i in range(record_index + 1, len(records))
                            if records[i]["agent_id"] == record["agent_id"]), None)
        following = records[later_index] if later_index is not None else None
        for call_index, call in enumerate(record["response"].get("tool_calls") or []):
            if action_index >= len(actions):
                alignment_errors.append("unexecuted call at record " + str(record_index))
                continue
            action = actions[action_index]
            function = call.get("function", call)
            call_id = str(call.get("id") or f"call-{record_index + 1}-{call_index}")
            position = len(record["request"]["messages"]) + 1 + call_index
            if (action["seq"] != action_index + 1 or action["actor"] != record["agent_id"]
                    or action["turn"] != record["turn"] or action["tool"] != function.get("name")):
                alignment_errors.append("action/call mismatch at action " + str(action_index))
            elif following is None or len(following["request"]["messages"]) <= position:
                unavailable += 1
            else:
                message = following["request"]["messages"][position]
                if message.get("role") != "tool" or message.get("tool_call_id") != call_id:
                    alignment_errors.append("tool observation mismatch at action " + str(action_index))
                else:
                    try:
                        observed = json.loads(message["content"])
                    except (json.JSONDecodeError, TypeError, KeyError):
                        alignment_errors.append("non-JSON tool observation at action " + str(action_index))
                    else:
                        compared += 1
                        if canonical_sha256(observed) != canonical_sha256(action["result"]):
                            changed = sorted(key for key in set(observed) | set(action["result"])
                                             if observed.get(key) != action["result"].get(key)) if isinstance(observed, dict) else []
                            findings.append({"action_index": action_index, "record_index": record_index,
                                "actor": action["actor"], "tool": action["tool"], "turn": action["turn"],
                                "changed_fields": changed,
                                "recorded_result_pointer": f"/actions/{action_index}/result",
                                "observed_tool_pointer": f"/records/{later_index}/request/messages/{position}/content",
                                "recorded_result_sha256": canonical_sha256(action["result"]),
                                "sut_observed_result_sha256": canonical_sha256(observed)})
            action_index += 1
    if action_index != len(actions):
        alignment_errors.append("action count differs from retained response calls")
    return {"actions": len(actions), "compared": compared,
            "not_observed_in_a_later_request": unavailable,
            "mismatches": findings, "alignment_errors": alignment_errors}
