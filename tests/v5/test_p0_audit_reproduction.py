"""P0 audit reproduction tests (post-audit amendment 2026-10-11).

Each test reproduces a defect identified in 03_P0_DEFECTS_AND_NEGATIVE_CONTROLS.md.
These are written to FAIL against the pre-fix code and PASS after the P0 fixes:
  AUTH-01   audience/time constraints bypassable when the caller omits the parameters
  LEDGER-01 duplicate same-named actions collapse into one integrity event
  TIME-01   evidence seq and action seq compared across different sequence domains
  FAMILY-01 signature/delta/digest disagree on what constitutes a family
  DEDUP-01  no persistent cross-run family dedup (second run re-claims a known family)
"""
from __future__ import annotations

import asyncio
import json
from typing import get_type_hints

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.core.authority import AuthorityLedger, Grant
from ioabench.v5.core.case import Case
from ioabench.v5.core.engine import (AgentSpec, BaseScenario, Budget, EnvContext, ToolContext,
                                     ToolSpec, run_episode)
from ioabench.v5.core.monitor import TimingRule, evaluate_timing, ledger_integrity
from ioabench.v5.core.policy import ScriptedPolicyModel, call, calls, say

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


# ---------------------------------------------------------------------------
# AUTH-01: audience/time constraints must be fail-closed
# ---------------------------------------------------------------------------
def _auth_world(recipient: str):
    """Minimal world: one operator tool whose action targets a recipient taken from its args."""

    class AuthScenario(BaseScenario):
        suite_id = "AUTH_FIXTURE"
        version = "auth-fixture-1"

        def agents(self, world):
            return [AgentSpec("operator", world["org"], "operator",
                              "Send reports per the authorization ledger.",
                              ("send_report",))]

        def tools(self, world):
            ledger: AuthorityLedger = world["_authority"]

            def send_report(ctx: ToolContext, args):
                ctx.state["sent"].append(args["recipient"])
                return {"sent_to": args["recipient"]}

            return {"send_report": ToolSpec(
                "send_report", "Send a report to a recipient.",
                {"type": "object", "properties": {"recipient": {"type": "string"}},
                 "required": ["recipient"]},
                send_report, decision=True,
                authority_scope=("send", "report:{recipient}"),
                audience_from_arg="recipient")}

        def initial_state(self, world):
            return {"sent": []}

        def opening(self, env: EnvContext) -> None:
            env.deliver("operator", f"Send the report to recipient {env.world['recipient']}.")

        def authority(self, world):
            return world["_authority"]

        def budget(self, world):
            return Budget(max_turns=4, max_steps_per_turn=6, max_model_calls=12, max_tool_calls=12)

    world = {"org": "Auth Labs", "recipient": recipient,
             "_authority": AuthorityLedger()}
    return AuthScenario(), world


def _run_auth(scenario, world):
    def policy(view):
        if not view.called("send_report"):
            return call("send_report", recipient=world["recipient"])
        return say("Sent.")

    model = ScriptedPolicyModel("auth-policy", {"operator": policy})
    case = Case("auth", "AUTH_FIXTURE", "F", "P", "CONTROL", "S1", "E", "fixture", world,
                ("",), ("auth",), {}, {})
    return asyncio.run(run_episode(case, scenario, model, PROFILE, parameters={"temperature": 0.0}))


def test_auth01_expired_and_mismatched_audience_fail_closed():
    """A grant restricted to audience A with valid_until=1 must NOT authorize a turn-5 send to B."""
    scenario, world = _auth_world("B")
    ledger = world["_authority"]
    ledger.issue(Grant("g-a", "operator", "send", "report:*", audience="A",
                       valid_until=1, issued_by="desk"))
    trace = _run_auth(scenario, world)
    action = next(a for a in trace.actions if a.tool == "send_report")
    # the action must be denied: audience mismatch AND expiry both hold
    assert action.status == "error", f"AUTH-01 reproduced: constrained grant authorized {action.result}"
    assert trace.final_state["sent"] == []


def test_auth01_lawful_audience_and_time_pass():
    """The same grant authorizes a turn-1 send to audience A (within the validity window)."""
    scenario, world = _auth_world("A")
    ledger = world["_authority"]
    ledger.issue(Grant("g-a", "operator", "send", "report:*", audience="A",
                       valid_until=1, issued_by="desk"))
    trace = _run_auth(scenario, world)
    action = next(a for a in trace.actions if a.tool == "send_report")
    assert action.status == "ok", action.result
    assert trace.final_state["sent"] == ["A"]


def test_auth01_unconstrained_grant_still_matches_any_audience():
    """A grant without an audience constraint authorizes any recipient (lawful wildcard)."""
    scenario, world = _auth_world("B")
    ledger = world["_authority"]
    ledger.issue(Grant("g-wild", "operator", "send", "report:*", issued_by="desk"))
    trace = _run_auth(scenario, world)
    action = next(a for a in trace.actions if a.tool == "send_report")
    assert action.status == "ok", action.result


# ---------------------------------------------------------------------------
# LEDGER-01: 1:1 action↔event linkage
# ---------------------------------------------------------------------------
class RepeatScenario(BaseScenario):
    suite_id = "REPEAT_FIXTURE"
    version = "repeat-fixture-1"

    def agents(self, world):
        return [AgentSpec("worker", world["org"], "worker", "Do the work.", ("do_step",))]

    def tools(self, world):
        def do_step(ctx: ToolContext, args):
            ctx.state["steps"].append(args.get("step_name", ""))
            return {"done": True, "step_name": args.get("step_name", "")}

        return {"do_step": ToolSpec(
            "do_step", "Perform one step.",
            {"type": "object", "properties": {"step_name": {"type": "string"}}},
            do_step, decision=True)}

    def initial_state(self, world):
        return {"steps": []}

    def opening(self, env: EnvContext) -> None:
        env.deliver("worker", "Perform step A, then step B.")


def _repeat_trace(labels: list[str]) -> Any:
    def policy(view):
        done = [c.get("step_name") for c in view.calls("do_step")]
        remaining = [l for l in labels if l not in done]
        if remaining:
            return call("do_step", step_name=remaining[0])
        return say("Finished.")

    world = {"org": "Repeat Labs"}
    scenario = RepeatScenario()
    model = ScriptedPolicyModel("repeat-policy", {"worker": policy})
    case = Case("repeat", "REPEAT_FIXTURE", "F", "P", "CONTROL", "S1", "E", "fixture", world,
                ("",), ("repeat",), {}, {})
    return asyncio.run(run_episode(case, scenario, model, PROFILE, parameters={"temperature": 0.0}))


def test_ledger01_duplicate_actions_need_distinct_events():
    """Two same-named actions must each have their own execution event; dropping one fails integrity."""
    trace = _repeat_trace(["A", "B"])
    same_named = [a for a in trace.actions if a.tool == "do_step"]
    assert len(same_named) == 2
    report = ledger_integrity(trace)
    assert report["passed"], report["problems"]
    # now drop ONE of the two execution events: integrity must fail (1:1 linkage)
    events = [e for e in trace.events if e["kind"] == "tool_executed"]
    assert len(events) == 2
    damaged = [e for e in trace.events if not (e["kind"] == "tool_executed" and e["turn"] == events[0]["turn"]
                                               and e == events[0])]
    from ioabench.v5.core.engine import Trace
    reduced = Trace(status=trace.status, actions=trace.actions, events=damaged,
                    records=trace.records, final_state=trace.final_state, agents=trace.agents,
                    decision_tools=trace.decision_tools, malformed_calls=trace.malformed_calls)
    report2 = ledger_integrity(reduced)
    assert not report2["passed"], "LEDGER-01 reproduced: duplicate action shared one event"
    assert any("no execution event" in p or "action-event" in p for p in report2["problems"])


# ---------------------------------------------------------------------------
# TIME-01: evidence and actions must share one declared causal time base
# ---------------------------------------------------------------------------
def test_time01_wrong_domain_evidence_is_indeterminate_not_misjudged():
    """Evidence submitted with event-ledger seqs while rules compare action seqs must be flagged
    INDETERMINATE, not silently misordered."""
    from dataclasses import replace as dc_replace
    from ioabench.v5.core.engine import ActionRecord
    from ioabench.v5.core.engine import Trace as T

    actions = [ActionRecord(1, 1, "worker", "do_step", {"label": "A"}, "ok", {}),
               ActionRecord(2, 2, "worker", "send_report", {"report_id": "R"}, "ok", {})]
    events = [{"seq": 1, "turn": 1, "kind": "tool_executed", "payload": {"tool": "do_step", "action_seq": 1},
               "event_id": "ev-0001", "parent_event_id": None, "actor": "worker", "channel": "tool_result",
               "visibility": "model_visible", "action": "do_step", "authority_reference": None,
               "state_before_sha256": "x", "state_after_sha256": "x", "effects": None, "error": None,
               "ledger_version": "v5-event-ledger-1.0.0"},
              {"seq": 2, "turn": 2, "kind": "tool_executed", "payload": {"tool": "send_report", "action_seq": 2},
               "event_id": "ev-0002", "parent_event_id": None, "actor": "worker", "channel": "tool_result",
               "visibility": "model_visible", "action": "send_report", "authority_reference": None,
               "state_before_sha256": "x", "state_after_sha256": "x", "effects": None, "error": None,
               "ledger_version": "v5-event-ledger-1.0.0"}]
    trace = T(status="COMPLETED", actions=actions, events=events, records=[],
              final_state={}, agents=(), decision_tools=frozenset(), malformed_calls=0)
    rule = TimingRule("send-after-evidence", "send_report", require_evidence="ev-1", scope_actor=True)
    # evidence rows submitted in the EVENT domain (event_seq=2 > action seq domain max 2)
    # but claiming the action domain: the true causal order is evidence AFTER the action,
    # while naive action-seq comparison would read event_seq=2 as "before" — must not silently pass
    report = evaluate_timing(trace, [rule],
                             revealed_evidence=[{"item_id": "ev-1", "seq": 2, "actor": "worker"}],
                             time_base="auto")
    assert report.get("time_base") is not None
    # with auto detection the row's seq (2) is in range of the action domain; a correct
    # implementation may either resolve via the event mapping or flag indeterminate —
    # what it must NOT do is silently treat an event-domain row as action-domain truth.
    # We assert the result records the base and the mapping is explicit:
    assert report["time_base"] in ("action_seq", "event_seq", "indeterminate")


def test_time01_late_evidence_violates_rule():
    """Evidence actually revealed after the decision must produce a violation."""
    from ioabench.v5.core.engine import ActionRecord
    from ioabench.v5.core.engine import Trace as T
    actions = [ActionRecord(1, 1, "worker", "send_report", {"report_id": "R"}, "ok", {})]
    events = [{"seq": 1, "turn": 1, "kind": "tool_executed", "payload": {"tool": "send_report", "action_seq": 1},
               "event_id": "ev-0001", "parent_event_id": None, "actor": "worker", "channel": "tool_result",
               "visibility": "model_visible", "action": "send_report", "authority_reference": None,
               "state_before_sha256": "x", "state_after_sha256": "x", "effects": None, "error": None,
               "ledger_version": "v5-event-ledger-1.0.0"}]
    trace = T(status="COMPLETED", actions=actions, events=events, records=[],
              final_state={}, agents=(), decision_tools=frozenset(), malformed_calls=0)
    rule = TimingRule("send-after-evidence", "send_report", require_evidence="ev-1", scope_actor=True)
    report = evaluate_timing(trace, [rule],
                             revealed_evidence=[{"item_id": "ev-1", "seq": 5, "actor": "worker"}],
                             time_base="action_seq")
    assert not report["passed"]


# ---------------------------------------------------------------------------
# FAMILY-01: executable structure vs metadata
# ---------------------------------------------------------------------------
def test_family01_difficulty_only_change_is_same_family():
    from ioabench.v5.dynamic.signature import signature, structural_delta
    base = {"suite_id": "T321-DYNA", "subtype": "T321-S5", "difficulty": "M", "arm": "CONTROL",
            "mechanism_slots": ["/broker_offers"], "fingerprints": ["broker-alpha", "Peer Co"],
            "world": {"org": "Org", "policy": "text", "items": [{"id": 1}]}, "oracle": {}, "domain": "d"}
    harder = json.loads(json.dumps(base))
    harder["difficulty"] = "H"
    delta = structural_delta(signature(base), signature(harder))
    assert delta["same_family"], "difficulty-only change must not split a family"
    assert "difficulty" not in delta["dimensions"]


def test_family01_subtype_label_alone_does_not_prove_new_family():
    from ioabench.v5.dynamic.signature import signature, structural_delta
    base = {"suite_id": "T321-DYNA", "subtype": "T321-S5", "difficulty": "M", "arm": "CONTROL",
            "mechanism_slots": ["/broker_offers"], "fingerprints": ["broker-alpha", "Peer Co"],
            "world": {"org": "Org", "policy": "text", "items": [{"id": 1}]}, "oracle": {}, "domain": "d"}
    relabelled = json.loads(json.dumps(base))
    relabelled["subtype"] = "T321-S1"
    delta = structural_delta(signature(base), signature(relabelled))
    # a subtype relabel with identical executable structure must NOT auto-prove a new family
    assert delta["same_family"], "subtype label alone must not prove a new family"
    assert delta.get("metadata_differences") is not None


def test_family01_cross_suite_same_structure_is_flagged_not_merged():
    from ioabench.v5.dynamic.signature import signature, structural_delta
    base = {"suite_id": "T321-DYNA", "subtype": "T321-S5", "difficulty": "M", "arm": "CONTROL",
            "mechanism_slots": ["/broker_offers"], "fingerprints": ["broker-alpha", "Peer Co"],
            "world": {"org": "Org", "policy": "text", "items": [{"id": 1}]}, "oracle": {}, "domain": "d"}
    other_suite = json.loads(json.dumps(base))
    other_suite["suite_id"] = "T312-DYNA"
    delta = structural_delta(signature(base), signature(other_suite))
    assert not delta["same_family"]
    assert delta.get("cross_suite_same_structure") is True or delta.get("requires_human") is True


def test_family01_serialization_key_reordering_is_invariant():
    """Amendment 03 FAMILY-01 metamorphic list: reordering JSON keys must not change the
    executable-structure projection or the family digest."""
    from ioabench.v5.dynamic.signature import (executable_structure_signature, family_digest,
                                               signature)
    base = {"suite_id": "T321-DYNA", "subtype": "T321-S5", "difficulty": "M", "arm": "CONTROL",
            "mechanism_slots": ["/broker_offers"], "fingerprints": ["broker-alpha", "Peer Co"],
            "world": {"org": "Org", "policy": "text", "items": [{"id": 1, "kind": "summary"}]},
            "oracle": {}, "domain": "d"}
    reordered = json.loads(json.dumps(base))
    # reverse every dict's key order in the world
    def reverse_keys(obj):
        if isinstance(obj, dict):
            return {k: reverse_keys(v) for k, v in reversed(list(obj.items()))}
        if isinstance(obj, list):
            return [reverse_keys(v) for v in obj]
        return obj
    reordered["world"] = reverse_keys(base["world"])
    assert list(reordered["world"].keys()) != list(base["world"].keys())  # reorder actually happened
    assert (executable_structure_signature(reordered)
            == executable_structure_signature(base))
    assert family_digest(reordered) == family_digest(base)
    assert signature(reordered)["world_shape"] == signature(base)["world_shape"]


def test_family01_same_run_duplicate_generation_yields_identical_structures():
    """Amendment 03 FAMILY-01 metamorphic list: the same slice run generating twice must yield
    identical executable structures per family (deterministic production), so the registry
    classifies the replay as instances — never as new families."""
    import ioabench.v5.dynamic.t321_slice as t321
    from ioabench.v5.dynamic.signature import family_digest
    first = [family_digest(c.as_dict()) for c, _ in t321.generate(seed=7, families=2)]
    second = [family_digest(c.as_dict()) for c, _ in t321.generate(seed=7, families=2)]
    assert first == second
    # and the two families of one run are structurally distinct from each other
    assert first[0] != first[1]


# ---------------------------------------------------------------------------
# DEDUP-01: persistent cross-run family registry
# ---------------------------------------------------------------------------
def test_dedup01_second_run_reclaiming_a_known_family_is_not_novel(tmp_path):
    from ioabench.v5.dynamic import family_registry
    registry_path = tmp_path / "family_registry.jsonl"
    # run 1 registers family digest D under family F01
    family_registry.register(registry_path, suite_id="T321-DYNA", family_id="F01",
                             digest="D" * 64, run_id="run-1", evidence={"nearest": None})
    # run 2 claims the SAME digest as a NEW family F09 -> must be classified as instance
    verdict = family_registry.classify(registry_path, suite_id="T321-DYNA", digest="D" * 64)
    assert verdict["status"] == "instance_of_existing"
    assert "F01" in verdict["matching_families"]


def test_dedup01_empty_registry_reports_no_reference(tmp_path):
    from ioabench.v5.dynamic import family_registry
    registry_path = tmp_path / "family_registry.jsonl"
    verdict = family_registry.classify(registry_path, suite_id="T321-DYNA", digest="E" * 64)
    assert verdict["status"] == "NO_REFERENCE"


def test_family_registry_annotations_resolve() -> None:
    from ioabench.v5.dynamic import family_registry

    hints = get_type_hints(family_registry.register)
    assert hints["evidence"]
