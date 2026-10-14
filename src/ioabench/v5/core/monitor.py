"""Global monitoring primitives over the causal event ledger (dynamic-world phase M3).

Three generic, deterministic measurements — no LLM judge, no suite semantics baked in:

* ``ledger_integrity`` — structural invariants of an episode's event ledger (completeness of
  execution events, resolvable causal parents, contiguous sequence, presence of state hashes).
  A ledger that fails integrity cannot support behavioral claims (02_RUNTIME §6 item 4).
* ``evaluate_timing`` — pre-registered ordering properties ("no decision before the lawful
  evidence was visible"): each rule names a decision tool and what must have happened earlier
  (an ok use of a verification tool, or a revealed evidence item). Suites register their own
  rules; this module only evaluates them from the ledger.
* ``message_flow`` — pairs every enqueued world message with its model-visible delivery per
  agent and turn, the substrate for propagation measurement (T331-class chains are built on
  this by suite adapters).

All three consume only what the controlled environment captured. Unobserved states are
reported as such (empty/None), never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ioabench.v5.core.engine import Trace

MONITOR_VERSION = "v5-monitor-1.0.0"


def ledger_integrity(trace: Trace) -> dict[str, Any]:
    """Structural integrity report for an episode's event ledger.

    Post-audit LEDGER-01: actions and their execution events must be 1:1 linked via the
    ``action_seq`` recorded in each ``tool_executed`` event payload (engine >= 1.3.0). Legacy
    traces whose events lack that linkage fall back to an explicit legacy-compatible mode
    (set-based matching + a visible caveat) instead of pretending a verified 1:1 association.
    """
    events = trace.events
    problems: list[str] = []
    seqs = [e.get("seq") for e in events]
    if seqs != list(range(1, len(events) + 1)):
        problems.append(f"event seq is not contiguous 1..n: {seqs[:10]}...")
    ids = {e.get("event_id") for e in events}
    for event in events:
        parent = event.get("parent_event_id")
        if parent is not None and parent not in ids:
            problems.append(f"{event.get('event_id')}: unresolvable parent {parent}")
        if event.get("kind") == "tool_executed":
            for field in ("actor", "action", "state_before_sha256", "state_after_sha256", "visibility"):
                if not event.get(field):
                    problems.append(f"{event.get('event_id')}: tool_executed missing {field}")
    action_events = [e for e in events if e.get("kind") == "tool_executed"]
    linked = [e for e in action_events if isinstance(e.get("payload"), Mapping)
              and e["payload"].get("action_seq") is not None]
    legacy_mode = bool(action_events) and not linked
    if legacy_mode:
        # legacy-compatible audit: set-based matching with an explicit caveat, not a
        # fabricated 1:1 association
        executed = {(e.get("actor"), e.get("action")) for e in action_events}
        for action in trace.actions:
            if (action.actor, action.tool) not in executed:
                problems.append(f"action seq={action.seq} ({action.actor}/{action.tool}) has no execution event")
        result = {"monitor_version": MONITOR_VERSION, "check": "ledger_integrity",
                  "events": len(events), "actions": len(trace.actions),
                  "action_event_linkage": "legacy_set_based",
                  "legacy_mode": True,
                  "passed": not problems, "problems": problems}
        return result
    # 1:1 linkage mode: every action maps to exactly one tool_executed event via action_seq,
    # and every linked event maps back to an existing action
    by_action_seq: dict[int, list[dict[str, Any]]] = {}
    for event in action_events:
        action_seq = event["payload"].get("action_seq")
        by_action_seq.setdefault(int(action_seq), []).append(event)
    for action in trace.actions:
        matches = by_action_seq.get(action.seq, [])
        if not matches:
            problems.append(f"action seq={action.seq} ({action.actor}/{action.tool}) has no execution event")
        elif len(matches) > 1:
            problems.append(f"action seq={action.seq} has {len(matches)} execution events (must be exactly one)")
        else:
            event = matches[0]
            if event.get("actor") != action.actor or event.get("action") != action.tool:
                problems.append(f"action seq={action.seq} linked to a mismatched execution event "
                                f"({event.get('actor')}/{event.get('action')})")
    orphan_events = [e for e in action_events
                     if int(e["payload"].get("action_seq", -1)) not in {a.seq for a in trace.actions}]
    for event in orphan_events:
        problems.append(f"{event.get('event_id')}: execution event references a non-existent action "
                        f"seq {event['payload'].get('action_seq')}")
    return {"monitor_version": MONITOR_VERSION, "check": "ledger_integrity",
            "events": len(events), "actions": len(trace.actions),
            "action_event_linkage": "one_to_one_action_seq",
            "legacy_mode": False,
            "passed": not problems, "problems": problems}


@dataclass(frozen=True)
class TimingRule:
    """One pre-registered ordering property.

    ``decision_tool``: the tool whose ok executions must be preceded by the requirement.
    ``require_tool``: an ok execution of this tool earlier in the episode satisfies the rule.
    ``require_evidence``: revelation of this evidence item earlier satisfies the rule
    (matched against evidence-reveal rows, see ``evaluate_timing``).
    ``scope_actor``: require the predecessor by the same actor (default False: any agent's
    earlier verification counts, e.g. a colleague's lookup in a shared record).
    ``when_args``: restrict the rule to actions whose arguments match — each key must be
    present with the given value; the wildcard ``"*"`` means "key present with any value".
    Rules without ``when_args`` apply to every ok execution of the tool.
    """
    name: str
    decision_tool: str
    require_tool: str | None = None
    require_evidence: str | None = None
    scope_actor: bool = False
    when_args: Mapping[str, Any] | None = None

    def applies_to(self, arguments: Mapping[str, Any]) -> bool:
        if self.when_args is None:
            return True
        return all(key in arguments and (expected == "*" or arguments.get(key) == expected)
                   for key, expected in self.when_args.items())


def evaluate_timing(trace: Trace, rules: Sequence[TimingRule],
                    revealed_evidence: Sequence[Mapping[str, Any]] = (),
                    time_base: str = "auto") -> dict[str, Any]:
    """Evaluate timing rules over an episode.

    Post-audit TIME-01: actions and evidence must be compared in ONE declared causal time
    base. ``time_base`` selects it explicitly:

    * ``"action_seq"`` — evidence rows carry ``seq`` in the ActionRecord.seq domain;
    * ``"event_seq"``  — evidence rows carry ``event_seq`` in the event-ledger domain and each
      candidate action is resolved to its ``tool_executed`` event via the payload ``action_seq``
      linkage, so both sides compare in the ledger's causal order;
    * ``"auto"``       — inferred: event-domain when evidence rows carry ``event_seq`` or when
      any row's ``seq`` exceeds the action-seq range (which would be unrepresentable in the
      action domain); otherwise action_seq.

    Rows that cannot be located in the selected base are reported under ``indeterminate`` and
    fail the affected rules as unverifiable rather than silently ordering them.
    """
    events = trace.events
    max_action_seq = max((a.seq for a in trace.actions), default=0)
    if time_base == "auto":
        has_event_seq = any("event_seq" in r for r in revealed_evidence)
        out_of_action_range = any(int(r["seq"]) > max_action_seq
                                  for r in revealed_evidence if "seq" in r and "event_seq" not in r)
        time_base = "event_seq" if (has_event_seq or out_of_action_range) else "action_seq"
    if time_base not in ("action_seq", "event_seq"):
        raise ValueError(f"unknown time_base {time_base!r}")
    # resolve each ok action to its causal position in the selected base
    tool_executed_by_action_seq: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("kind") == "tool_executed" and isinstance(event.get("payload"), Mapping) \
                and event["payload"].get("action_seq") is not None:
            tool_executed_by_action_seq[int(event["payload"]["action_seq"])] = event

    def action_position(seq: int) -> int:
        if time_base == "action_seq":
            return seq
        event = tool_executed_by_action_seq.get(seq)
        return int(event["seq"]) if event else seq  # unlinked actions compare in action domain

    tool_oks: list[tuple[int, int, str, str]] = []
    for a in trace.actions:
        if a.status == "ok":
            tool_oks.append((action_position(a.seq), a.seq, a.actor, a.tool))
    reveals: list[tuple[int, str, str]] = []
    indeterminate: list[dict[str, Any]] = []
    for r in revealed_evidence:
        if "event_seq" in r:
            if time_base == "event_seq":
                reveals.append((int(r["event_seq"]), str(r.get("actor", "")), str(r["item_id"])))
            else:
                indeterminate.append({"row": dict(r),
                                      "reason": "event_seq supplied but time_base is action_seq"})
        else:
            seq_value = int(r["seq"])
            if time_base == "action_seq":
                reveals.append((seq_value, str(r.get("actor", "")), str(r["item_id"])))
            else:
                # an action-domain row cannot be ordered in the event domain without a mapping
                indeterminate.append({"row": dict(r),
                                      "reason": "seq supplied but time_base is event_seq"})
    violations: list[dict[str, Any]] = []
    for rule in rules:
        for pos, action_seq, actor, tool in tool_oks:
            if tool != rule.decision_tool:
                continue
            arguments = next((a.arguments for a in trace.actions if a.seq == action_seq), {})
            if not rule.applies_to(arguments):
                continue
            satisfied = False
            if rule.require_tool is not None:
                satisfied = any(p_pos < pos and (not rule.scope_actor or p_actor == actor)
                                and p_tool == rule.require_tool
                                for p_pos, _p_aseq, p_actor, p_tool in tool_oks)
            if not satisfied and rule.require_evidence is not None:
                satisfied = any(r_seq < pos and (not rule.scope_actor or r_actor == actor)
                                and r_item == rule.require_evidence
                                for r_seq, r_actor, r_item in reveals)
            if not satisfied:
                violations.append({"rule": rule.name, "action_seq": action_seq, "actor": actor,
                                   "tool": tool, "detail": f"{rule.decision_tool} at action seq {action_seq} without "
                                   f"prior {rule.require_tool or rule.require_evidence}"})
    passed = not violations and not indeterminate
    return {"monitor_version": MONITOR_VERSION, "check": "timing_properties",
            "time_base": time_base,
            "indeterminate": indeterminate,
            "rules": [rule.name for rule in rules], "violations": violations,
            "passed": passed}


def message_flow(trace: Trace) -> dict[str, Any]:
    """Pair enqueued world messages with their model-visible deliveries (FIFO per agent).

    The engine records ``message_enqueued`` (environment visibility) on ``EnvContext.deliver``
    — at the SENDER's turn — and ``message_delivered`` (model-visible) when the recipient's
    turn consumes its inbox, possibly several turns later. Matching is therefore FIFO per
    recipient agent, not per turn.
    """
    pending: dict[str, list[dict[str, Any]]] = {}
    flows: list[dict[str, Any]] = []
    for event in trace.events:
        kind = event.get("kind")
        if kind == "message_enqueued":
            recipient = str(event.get("payload", {}).get("to", ""))
            pending.setdefault(recipient, []).append(event)
        elif kind == "message_delivered":
            agent = str(event.get("actor", ""))
            queue = pending.get(agent)
            if queue:
                enqueued = queue.pop(0)
                flows.append({"enqueued_seq": enqueued["seq"], "delivered_seq": event["seq"],
                              "agent": agent, "enqueued_turn": enqueued["turn"],
                              "delivered_turn": event["turn"]})
            else:
                flows.append({"enqueued_seq": None, "delivered_seq": event["seq"],
                              "agent": agent, "enqueued_turn": None,
                              "delivered_turn": event["turn"], "note": "delivery without matched enqueue"})
    unmatched = [{"agent": agent, "turn": row["turn"], "enqueued_seq": row["seq"]}
                 for agent, rows in pending.items() for row in rows]
    return {"monitor_version": MONITOR_VERSION, "check": "message_flow",
            "flows": flows, "undelivered_enqueues": unmatched,
            "paired": sum(1 for f in flows if f["enqueued_seq"] is not None)}
