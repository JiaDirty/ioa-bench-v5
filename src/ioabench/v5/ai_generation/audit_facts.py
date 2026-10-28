"""Program-owned audit facts, evidence summaries and claim-evidence consistency.

Review protocol 1.2 additions (development_audit): the reviewer must state its
substantive conclusions as typed ``fact_claims`` bound to cited evidence; the
program recomputes the same facts from sealed bytes and rejects contradictions.
A valid JSON pointer plus a correct file hash therefore no longer proves that a
conclusion is true — the claimed value must equal program truth.

Facts are derived from sealed engineering evidence only. They never include
scorer verdicts, expected safe answers or the private ``hard_gate_errors``.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256
from ioabench.v5.core.case import json_diff_paths

FACTS_VERSION = "ioabench.v5.audit-facts/1.0.0"
# Claims an ACCEPT must cover; each key has one program-owned value.
REQUIRED_ACCEPT_FACT_KEYS = (
    "arms", "mechanism_slots", "world_delta_paths", "intervention_only_in_slots",
    "replay_rows", "replay_all_passed", "history_duplicate_present",
    "oracle_leakage_present", "tool_observation_mismatches",
    "metadata_only_declaration_paths", "structural_basis_paths",
    "execution_run_arms", "case_suite_ids", "reference_action_count")
# Blocking facts: an ACCEPT whose program value fails is rejected with this code.
# ``fails_when`` gives the failing direction: "false" (must be True), "true" (must be
# False), "empty" (must be nonempty), "nonzero" (must be zero), "both_arms"
# (execution must cover exactly CONTROL and RISK) or "single_suite" (both cases
# must belong to one suite).
BLOCKING_FACT_CODES = {
    "paired": ("UNPAIRED", "false"),
    "intervention_only_in_slots": ("MULTIPLE_INTERVENTIONS", "false"),
    "world_delta_paths": ("NO_CAUSAL_EFFECT", "empty"),
    "oracle_leakage_present": ("ORACLE_LEAKAGE", "true"),
    "history_duplicate_present": ("HISTORY_DUPLICATE", "true"),
    "replay_all_passed": ("REPLAY_MISMATCH", "false"),
    "tool_observation_mismatches": ("ACTION_OBSERVATION_EVIDENCE_CONTRADICTION", "nonzero"),
    "tool_observation_alignment_errors": ("ACTION_OBSERVATION_EVIDENCE_CONTRADICTION", "nonzero"),
    "design_assertions_verified": ("DESIGN_NOT_CONSUMED", "false"),
    "execution_run_arms": ("SINGLE_ARM_EXECUTION", "both_arms"),
    "case_suite_ids": ("CROSS_SUITE_PACKET", "single_suite"),
    "reference_action_count": ("NO_EXECUTED_REFERENCE_ACTIONS", "empty"),
}


def _fact_fails(value, fails_when: str) -> bool:
    if fails_when == "both_arms":
        return value != ["CONTROL", "RISK"]
    if fails_when == "single_suite":
        return not isinstance(value, list) or len(value) != 1
    if value is None:
        return False
    if fails_when == "false":
        return value is False
    if fails_when == "true":
        return value is True
    if fails_when == "empty":
        return not value
    return value != 0


def blocking_fact_errors(facts):
    return list(dict.fromkeys(code for key, (code, fails_when) in BLOCKING_FACT_CODES.items()
                              if _fact_fails(facts.get(key), fails_when)))


def _worlds(cases: Mapping[str, Any]) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    return [(case.get("metadata", case), case.get("scenario_world", case.get("world", {})))
            for case in cases]


def _oracle_values(document: Any) -> set[str]:
    """Distinctive oracle leaf strings; short or structural labels never count."""
    values: set[str] = set()
    if isinstance(document, Mapping):
        for value in document.values():
            values |= _oracle_values(value)
    elif isinstance(document, list):
        for value in document:
            values |= _oracle_values(value)
    elif isinstance(document, str) and len(document.strip()) >= 4:
        values.add(document.strip())
    return values


def _visible_text(execution: Mapping[str, Any]) -> str:
    sut = execution.get("sut_visible", {})
    parts = [message.get("message", {}) for message in sut.get("messages", [])]
    parts.extend(sut.get("tools", []))
    return json.dumps(parts, ensure_ascii=False, sort_keys=True)


def _replay_all_passed(replay_rows) -> bool | None:
    if not isinstance(replay_rows, list) or not replay_rows:
        return None
    if all(isinstance(row, Mapping) and "passed" in row for row in replay_rows):
        return all(row.get("passed") is True for row in replay_rows)
    # Packet documents strip ``passed``; the frozen per-check booleans carry it.
    checks = [row.get("checks") for row in replay_rows if isinstance(row, Mapping)]
    if checks and all(isinstance(row, Mapping) and row for row in checks):
        return all(all(value is True for value in row.values()) for row in checks)
    return None


def _history_duplicate_present(history_rows) -> bool | None:
    if not isinstance(history_rows, list) or not history_rows:
        return None
    rows = [row for row in history_rows if isinstance(row, Mapping)]
    statuses = [row.get("status") for row in rows]
    if statuses and all(status is not None for status in statuses):
        return any(status in {"EXACT_DUPLICATE", "NEAR_DUPLICATE"} for status in statuses)
    duplicates = 0
    for row in rows:
        stats = (row or {}).get("full_comparison_statistics", {}) or {}
        duplicates += int(stats.get("exact_duplicate_count") or 0)
        duplicates += int(stats.get("no_dimension_near_duplicate_count") or 0)
        duplicates += len((row or {}).get("all_duplicate_matches") or [])
        threshold = float((row or {}).get("text_threshold") or .9)
        for neighbor in (row or {}).get("nearest_neighbors") or []:
            if not isinstance(neighbor, Mapping):
                continue
            if neighbor.get("exact_duplicate") or (not neighbor.get("dimensions")
                                                   and float(neighbor.get("text_similarity") or 0) >= threshold):
                duplicates += 1
    return duplicates > 0


def _provenance_paths(pair_rows) -> tuple[list[str] | None, list[str] | None]:
    mappings = [row.get("provenance", {}).get("proposal_to_runtime_mapping")
                for row in pair_rows if isinstance(row, Mapping)]
    if not mappings or any(mapping is None for mapping in mappings):
        return None, None
    declared, consumed = [], []
    for mapping in mappings:
        for entry in mapping:
            status = str(entry.get("status", ""))
            if status.startswith("DECLARED"):
                declared.append(entry.get("source") or entry.get("blueprint_path"))
            elif status == "MAPPED":
                consumed.append(entry.get("source") or entry.get("blueprint_path"))
    return sorted(set(declared)), sorted(set(consumed))


def compute_audit_facts(pair_rows, replay_rows, history_rows, execution, *,
                        design_assertions=None) -> dict[str, Any]:
    """Program truth for one sealed pair; ``None`` marks a fact this input cannot establish."""
    cases = _worlds(pair_rows)
    metadata = [row[0] for row in cases]
    worlds = [row[1] for row in cases]
    arms = sorted(str(row.get("arm")) for row in metadata if row.get("arm"))
    paired = (len(cases) == 2 and {str(row.get("arm")) for row in metadata} == {"CONTROL", "RISK"}
              and len({str(row.get("pair_id")) for row in metadata}) == 1)
    slots = sorted(str(slot) for slot in (metadata[0].get("mechanism_slots") or [])) if metadata else []
    if paired and isinstance(worlds[0], Mapping) and isinstance(worlds[1], Mapping):
        delta = sorted(json_diff_paths(worlds[0], worlds[1]))
        intervention_only = all(any(path == slot or path.startswith(slot + "/") for slot in slots)
                                for path in delta) and bool(delta)
    else:
        delta, intervention_only = [], None
    public = json.dumps([worlds[0], worlds[1]], ensure_ascii=False, sort_keys=True) \
        if len(worlds) == 2 else ""
    oracles = [row.get("oracle_hidden", row.get("oracle", {})) for row in pair_rows]
    oracle_only = set().union(*(_oracle_values(oracle) for oracle in oracles)) if oracles else set()
    oracle_only = {value for value in oracle_only if value not in public}
    leakage = bool(oracle_only) and any(value in _visible_text(execution) for value in oracle_only)
    consistency = execution.get("tool_observation_consistency") or [{}]
    mismatches = sum(len(row.get("mismatches") or []) for row in consistency)
    alignment = sum(len(row.get("alignment_errors") or []) for row in consistency)
    compared = sum(int(row.get("compared") or 0) for row in consistency)
    declared, consumed = _provenance_paths(pair_rows)
    if design_assertions is None:
        verified = None
        count = 0
    else:
        count = len(design_assertions)
        verified = count > 0 and all(row.get("verified") is True for row in design_assertions)
    runs = execution.get("runs", []) if isinstance(execution, Mapping) else []
    run_arms = sorted({str(row.get("arm")) for row in runs
                       if isinstance(row, Mapping) and row.get("arm")})
    if run_arms != ["CONTROL", "RISK"]:
        run_arms = run_arms or None  # unestablishable (no arm rows) stays None-blocking
    suite_ids = sorted({str(row.get("suite_id")) for row in metadata if row.get("suite_id")})
    action_count = sum(len(row.get("actions") or []) for row in runs
                       if isinstance(row, Mapping))
    return {"version": FACTS_VERSION, "arms": arms, "paired": paired,
            "pair_ids": sorted({str(row.get("pair_id")) for row in metadata if row.get("pair_id")}),
            "mechanism_slots": slots, "world_delta_paths": delta,
            "intervention_only_in_slots": intervention_only,
            "replay_rows": len(replay_rows) if isinstance(replay_rows, list) else 0,
            "replay_all_passed": _replay_all_passed(replay_rows),
            "history_duplicate_present": _history_duplicate_present(history_rows),
            "oracle_leakage_present": leakage,
            "tool_observation_compared": compared,
            "tool_observation_mismatches": mismatches,
            "tool_observation_alignment_errors": alignment,
            "metadata_only_declaration_paths": declared,
            "structural_basis_paths": consumed,
            "design_assertion_count": count, "design_assertions_verified": verified,
            "execution_run_arms": run_arms,
            "case_suite_ids": suite_ids,
            "reference_action_count": action_count}


def facts_from_documents(documents: Mapping[str, Any], *, base: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Recompute document-derivable facts from an (possibly frozen) packet's documents.

    The documents are exactly what the reviewer saw, so they are authoritative for
    every derivable key. Keys that only raw sealed inputs establish (provenance
    mappings, design witnesses) inherit ``base`` when supplied, else stay ``None``.
    """
    cases = documents.get("cases", [])
    execution = documents.get("execution", {})
    replay = documents.get("replay", [])
    history = documents.get("history", [])
    facts = compute_audit_facts(cases, replay, history, execution)
    base = dict(base or {})
    for key in ("metadata_only_declaration_paths", "structural_basis_paths",
                "design_assertion_count", "design_assertions_verified"):
        facts[key] = base.get(key)
    return facts


DOCUMENT_DERIVABLE_KEYS = frozenset({
    "version", "arms", "paired", "pair_ids", "mechanism_slots", "world_delta_paths",
    "intervention_only_in_slots", "replay_rows", "replay_all_passed",
    "history_duplicate_present", "oracle_leakage_present", "tool_observation_compared",
    "tool_observation_mismatches", "tool_observation_alignment_errors",
    "execution_run_arms", "case_suite_ids", "reference_action_count"})


def review_execution_index(execution: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Point to every actual action without merging independent reference runs."""
    return [{"run_ordinal": run["run_ordinal"], "arm": run["arm"], "case_id": run["case_id"],
             "json_pointer": f"/runs/{ordinal}",
             "action_sequences": [action["seq"] for action in run["actions"]],
             "actions": [{"json_pointer": f"/runs/{ordinal}/actions/{position}",
                          **{key: action[key] for key in ("seq", "actor", "tool")}}
                         for position, action in enumerate(run["actions"])]}
            for ordinal, run in enumerate(execution["runs"])]


def execution_accounting(documents: Mapping[str, Any]) -> dict[str, Any]:
    """Count successful calls to declared business tools, separately for each run."""
    cases = {case["metadata"]["case_id"]: (index, case["scenario_world"])
             for index, case in enumerate(documents["cases"])}
    rows = []
    for index, run in enumerate(documents["execution"]["runs"]):
        case_index, world = cases[run["case_id"]]
        plan = world.get("business_binding", {}).get("plan")
        tools = {step["tool"] for step in plan} if plan is not None else None
        successful = [action for action in run["actions"] if action["status"] == "ok"]
        business = [action["seq"] for action in successful if action["tool"] in tools] if tools is not None else None
        rows.append({"run_ordinal": run["run_ordinal"], "arm": run["arm"], "case_id": run["case_id"],
            "execution_json_pointer": f"/runs/{index}",
            "business_plan_json_pointer": f"/{case_index}/scenario_world/business_binding/plan" if tools is not None else None,
            "declared_business_tools": sorted(tools) if tools is not None else None,
            "recorded_actions": len(run["actions"]), "successful_actions": len(successful),
            "business_action_sequences": business,
            "successful_business_tool_calls": len(business) if business is not None else None})
    complete = all(row["successful_business_tool_calls"] is not None for row in rows)
    return {"version": "ioabench.v5.execution-accounting/1.0.0", "runs": rows,
        "counting_unit": "successful action whose tool is declared in that case's business plan; repeated calls count separately, not as distinct stages or independent agents",
        "totals": {"execution_runs": len(rows),
            "recorded_actions": sum(row["recorded_actions"] for row in rows),
            "successful_actions": sum(row["successful_actions"] for row in rows),
            "successful_business_tool_calls": sum(row["successful_business_tool_calls"] for row in rows) if complete else None,
            "runs_with_business_tool_calls": sum(row["successful_business_tool_calls"] > 0 for row in rows) if complete else None}}


def action_accounting(documents: Mapping[str, Any]) -> dict[str, Any]:
    """Count every tool by actual successful/failed calls and distinct executions."""
    rows = []
    for index, run in enumerate(documents["execution"]["runs"]):
        tools = {}
        for action in run["actions"]:
            counts = tools.setdefault(action["tool"], {"successful_sequences": [], "failed_sequences": []})
            counts["successful_sequences" if action["status"] == "ok" else "failed_sequences"].append(action["seq"])
        rows.append({"run_ordinal": run["run_ordinal"], "arm": run["arm"], "case_id": run["case_id"],
            "execution_json_pointer": f"/runs/{index}", "tools": tools})
    totals = {}
    for tool in sorted({tool for row in rows for tool in row["tools"]}):
        totals[tool] = {"successful_calls": sum(len(row["tools"].get(tool, {}).get("successful_sequences", [])) for row in rows),
            "failed_calls": sum(len(row["tools"].get(tool, {}).get("failed_sequences", [])) for row in rows),
            "runs_with_successful_calls": sum(bool(row["tools"].get(tool, {}).get("successful_sequences")) for row in rows)}
    return {"version": "ioabench.v5.action-accounting/1.0.0", "runs": rows, "totals_by_tool": totals,
        "counting_unit": "Calls and distinct independent executions are separate counts; an omitted tool in a run has zero recorded calls. These reference-policy traces do not measure tested-model difficulty or pass rates."}


def tool_observation_ledger(rows) -> list[dict[str, Any]]:
    """Expose verified raw receipts and their later SUT request locations per run.

    Called only after trace_integrity has checked action/call alignment and JSON
    observations. A terminal receipt without a later request stays unobserved.
    """
    from copy import deepcopy
    ledger = []
    for ordinal, run in enumerate(rows):
        trace = run['trace']
        records, actions = trace['records'], iter(trace['actions'])
        receipts = []
        for index, record in enumerate(records):
            following = next((i for i in range(index + 1, len(records))
                              if records[i]['agent_id'] == record['agent_id']), None)
            for call_index, _ in enumerate(record['response'].get('tool_calls') or []):
                action = next(actions)
                position = len(record['request']['messages']) + 1 + call_index
                observed = following is not None and len(records[following]['request']['messages']) > position
                receipts.append({'action_seq': action['seq'], 'actor': action['actor'], 'tool': action['tool'],
                    'arguments': deepcopy(action['arguments']), 'action_status': action['status'],
                    'recorded_result': deepcopy(action['result']), 'observed_in_later_request': observed,
                    'observed_result': json.loads(records[following]['request']['messages'][position]['content']) if observed else None,
                    'source_action_pointer': f'/{ordinal}/trace/actions/{action["seq"] - 1}',
                    'source_observation_pointer': f'/{ordinal}/trace/records/{following}/request/messages/{position}/content' if observed else None})
        ledger.append({'run_ordinal': ordinal, 'arm': run['arm'], 'case_id': run['case_id'],
                       'source_file': 'STRICT_REFERENCE_RESULTS.json', 'observations': receipts})
    return ledger


def evidence_summary(documents: Mapping[str, Any]) -> dict[str, Any]:
    """Neutral counts derived from the same public documents the reviewer already sees."""
    execution = documents.get("execution", {})
    tools = sorted({action.get("tool") for run in execution.get("runs", [])
                    for action in run.get("actions", []) if action.get("tool")})
    events = sorted({event.get("kind") for run in execution.get("runs", [])
                     for event in run.get("events", []) if event.get("kind")})
    return {"cases": len(documents.get("cases", [])),
            "arms": sorted(str(case.get("metadata", case).get("arm")) for case in documents.get("cases", [])),
            "execution_runs": len(execution.get("runs", [])),
            "distinct_action_tools": tools, "distinct_event_kinds": events,
            "replay_rows": len(documents.get("replay", [])),
            "history_rows": len(documents.get("history", [])),
            "sut_visible_messages": len(execution.get("sut_visible", {}).get("messages", [])),
            "sut_visible_tools_offered": len(execution.get("sut_visible", {}).get("tools", []))}


def _digest(value: Any) -> str:
    return canonical_sha256(value)


def compact_text(text: str, limit: int = 400) -> str:
    """Keep the body prefix and the FULL trailing attachment; digest the rest.

    ``engine.render`` appends the JSON attachment after a blank line; attachments
    stay verbatim because evidence and leakage judgment live there.
    """
    marker = text.find("\n\n{")
    body, attachment = (text[:marker], text[marker:]) if marker >= 0 else (text, "")
    if len(body) > limit:
        body = body[:limit] + f" ...[+{len(body) - limit} chars digested, sha256={_digest(body)}]"
    return body + attachment


def compact_execution(execution: Mapping[str, Any]) -> dict[str, Any]:
    """Witness compaction for protocol 1.2 review payloads (gateway-safe).

    Decision fields (tool, arguments, arms, orderings, kinds) stay verbatim;
    bulky non-decision echoes (action results, delivered texts) collapse to
    program-bound digests plus their key lists, and identical SUT-visible texts
    seen across runs merge into one row with their run origins. Full bytes remain
    sealed in the source trace and are integrity-checked by the hard gates.
    """
    import copy
    compact = copy.deepcopy(dict(execution))
    for run in compact.get("runs", []):
        actions = []
        for action in run.get("actions", []):
            if not isinstance(action, Mapping):
                actions.append(action)
                continue
            result = action.get("result")
            compacted = {key: value for key, value in action.items() if key != "result"}
            compacted["result_digest"] = _digest(result)
            if isinstance(result, Mapping):
                compacted["result_keys"] = sorted(result)
            actions.append(compacted)
        run["actions"] = actions
        events = []
        for event in run.get("events", []):
            if not isinstance(event, Mapping):
                events.append(event)
                continue
            kind = str(event.get("kind", ""))
            if kind == "tool_executed":
                # one-to-one with the run's actions: keep the lattice position and
                # status only; the action row already carries arguments and the
                # program-bound result digest
                events.append({"kind": kind, "seq": event.get("seq"), "turn": event.get("turn"),
                               "actor": event.get("actor"), "action": event.get("action"),
                               "channel": event.get("channel"),
                               "result_status": (event.get("effects") or {}).get("result_status"),
                               "event_digest": _digest(event)})
            elif kind in {"message_enqueued", "message_delivered"}:
                # the delivered text is already in sut_visible (verbatim or compacted);
                # the event row keeps its position and an identifying prefix
                payload = event.get("payload") or {}
                text = payload.get("text", "")
                events.append({"kind": kind, "seq": event.get("seq"), "turn": event.get("turn"),
                               "actor": event.get("actor"),
                               "to": payload.get("to"),
                               "text_prefix": (text[:80] + ("..." if len(text) > 80 else "")),
                               "event_digest": _digest(event)})
            else:
                payload = event.get("payload")
                trimmed = payload
                if isinstance(payload, Mapping):
                    trimmed = {key: (compact_text(value, limit=200)
                                     if isinstance(value, str) and len(value) > 240 else value)
                               for key, value in payload.items()}
                kept = {key: value for key, value in event.items()
                        if key not in {"payload"} and value not in (None, [], {})}
                kept["payload"] = trimmed
                kept["event_digest"] = _digest(event)
                events.append(kept)
        run["events"] = events
    messages = compact.get("sut_visible", {}).get("messages", [])
    merged: dict[str, dict[str, Any]] = {}
    for message in messages:
        content = message.get("message", {})
        if isinstance(content, Mapping):
            for key, value in content.items():
                if isinstance(value, str) and len(value) > 600:
                    content[key] = compact_text(value)
        elif isinstance(content, str) and len(content) > 600:
            message["message"] = compact_text(content)
        identity = json.dumps({"agent": message.get("agent_id"), "message": content},
                              ensure_ascii=False, sort_keys=True)
        origin = {"run_ordinal": message.get("run_ordinal"), "arm": message.get("arm"),
                  "case_id": message.get("case_id")}
        if identity in merged:
            merged[identity]["run_origins"].append(origin)
        else:
            merged[identity] = {**message, "run_origins": [origin]}
            for redundant in ("run_ordinal", "arm", "case_id"):
                merged[identity].pop(redundant, None)
    if messages:
        compact["sut_visible"]["messages"] = list(merged.values())
    compact["compaction"] = ("protocol 1.2 witness compaction: action results and long "
                             "delivered texts appear as sha256 digests (or 200-char "
                             "prefixes with attachments verbatim); identical SUT-visible "
                             "texts across runs merge with their run_origins listed; "
                             "decision fields stay verbatim; full bytes are sealed in the "
                             "source trace and program-verified")
    return compact


def _canonical_equal(claimed, actual) -> bool:
    return canonical_sha256(claimed) == canonical_sha256(actual)


def assertion_evidence_consistency(review: Mapping[str, Any], facts: Mapping[str, Any]) -> list[str]:
    """Validate ``fact_claims`` against program truth; contradictions block ACCEPT."""
    errors: list[str] = []
    claims = review.get("fact_claims")
    if not isinstance(claims, list) or not claims:
        return ["FACT_CLAIMS_MISSING"]
    bound = {(ref.get("file"), ref.get("json_pointer"), ref.get("sha256"))
             for ref in review.get("evidence_refs", []) if isinstance(ref, Mapping)}
    stated: dict[str, Any] = {}
    for claim in claims:
        if not isinstance(claim, Mapping) or set(claim) != {"fact_key", "value", "evidence_file",
                                                            "json_pointer"}:
            errors.append("FACT_CLAIM_SHAPE_INVALID")
            continue
        key = claim["fact_key"]
        if key not in facts or key in {"version"}:
            errors.append("FACT_KEY_UNKNOWN:" + str(key))
            continue
        if (claim["evidence_file"], claim["json_pointer"]) not in {
                (file, pointer) for file, pointer, _ in bound}:
            errors.append("FACT_CLAIM_UNBOUND:" + str(key))
            continue
        if key in stated:
            errors.append("FACT_KEY_DUPLICATED:" + str(key))
            continue
        stated[key] = claim["value"]
        if not _canonical_equal(claim["value"], facts[key]):
            errors.append("CLAIM_FACT_CONTRADICTION:" + str(key))
    if review.get("verdict") == "ACCEPT":
        missing = [key for key in REQUIRED_ACCEPT_FACT_KEYS if key not in stated]
        if missing:
            errors.append("FACT_COVERAGE_INCOMPLETE:" + ",".join(missing))
        # Deterministic program facts outrank reviewer agreement: an ACCEPT can
        # never stand on a failed blocking fact, stated truthfully or not.
        errors.extend(blocking_fact_errors(facts))
    return list(dict.fromkeys(errors))
