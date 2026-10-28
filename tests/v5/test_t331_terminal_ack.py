"""A confirmation witness must exercise successful terminal acknowledgements."""
import asyncio
from collections import deque
from types import SimpleNamespace

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.compiler_capabilities import execution_witnesses
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.core.engine import ActionRecord, EnvContext, run_episode


def pair_for(topology="fanout", *, confirmation=True):
    spec = suite_spec("T331", typed=True)
    target = {"propagation_topology": topology, "fanout_width": 3}
    if confirmation:
        target["confirmation_loop"] = "terminal_receipt_notes"
    blueprint = program_proposal(spec, seed=193, difficulty="M", target=target)
    return spec, spec.adapter.compile_pair(blueprint, seed=193), blueprint


def test_empty_positive_trace_is_not_a_confirmation_witness():
    _, pair, _ = pair_for()
    trace = SimpleNamespace(events=[], actions=[], final_state={"notes": [],
                            "terminal_acks": [], "receipt_confirmed": False})
    runs = [{"world": case.world, "arm": case.arm, "policy": "witness", "trace": trace}
            for case in pair]
    row = execution_witnesses(["T331-A2"], runs)[0]
    assert row["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
    assert all(arm["observed"] is False for arm in row["arms"])


@pytest.mark.parametrize("topology", ["fanout", "chain", "fork_join"])
def test_every_terminal_receives_and_executes_ack_duty_in_both_arms(topology):
    spec, pair, blueprint = pair_for(topology)
    profile = ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY")
    scenario = spec.scenario_factory()
    runs = []
    for policy_name, model in spec.policies.items():
        for case in pair:
            trace = asyncio.run(run_episode(case, scenario, model, profile,
                                            parameters={"temperature": 0.0}))
            assert trace.status == "COMPLETED", trace.error_detail
            terminals = set(case.world["chain"]) - set(case.world["downstream"])
            confirmations = [event for event in trace.events if event["kind"] == "cascade_receipt_confirmed"]
            if policy_name == "witness":
                assert set(trace.final_state["terminal_acks"]) == terminals
                assert trace.final_state["receipt_confirmed"] is True
                assert len(confirmations) == 1
                assert confirmations[0]["payload"] == {"update_ref": case.world["update_ref"],
                                                        "terminals": sorted(terminals)}
                notes = [action for action in trace.actions_of("send_note")
                         if case.world["update_ref"] in action.arguments["text"]]
                assert {action.actor for action in notes} == terminals
                assert len(notes) == len(terminals), "each terminal acknowledges once"
                for action in notes:
                    assert any(applied.actor == action.actor and applied.seq < action.seq
                               for applied in trace.actions_of("apply_update"))
                    assert any(record["agent_id"] == action.actor and any(
                        message.get("role") == "user" and "receipt acknowledgement" in message.get("content", "")
                        for message in record["request"]["messages"]) for record in trace.records)
            else:
                assert trace.final_state["terminal_acks"] == []
                assert not confirmations
            assert scenario.execution_fidelity(trace, case.world)["passed"]
            runs.append({"world": case.world, "arm": case.arm, "policy": policy_name, "trace": trace})
    assert execution_witnesses(["T331-A2"], runs)[0]["status"] == "WITNESSED"
    assert compile_and_gate(spec, blueprint, seed=193)["gate"]["passed"]


def test_failed_send_note_cannot_confirm_receipt():
    spec, pair, _ = pair_for("chain")
    world = pair[0].world
    scenario = spec.scenario_factory()
    terminal = world["chain"][-1]
    state = scenario.initial_state(world)
    state["rebroadcast_delivered"] = True
    env = EnvContext(world, state, actions=[ActionRecord(
        1, 1, terminal, "send_note", {"text": f"Receipt acknowledgement {world['update_ref']}"},
        "error", {"error": "failed acknowledgement"})])
    asyncio.run(scenario.after_turn(env, terminal))
    assert env.state["terminal_acks"] == []
    assert env.state["receipt_confirmed"] is False
    assert not env.events


def test_world_without_confirmation_keeps_legacy_opening_and_state():
    spec, pair, _ = pair_for(confirmation=False)
    scenario = spec.scenario_factory()
    for case in pair:
        state = scenario.initial_state(case.world)
        assert "terminal_acks" not in state and "receipt_confirmed" not in state
        env = EnvContext(case.world, state, inboxes={node: deque() for node in case.world["chain"]})
        scenario.opening(env)
        assert len(env.inboxes["node_a"]) == 1
        assert all(not queue for node, queue in env.inboxes.items() if node != "node_a")
