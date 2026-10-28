"""Finite discussion dependencies must execute, preserve pairing, and replay exactly."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler, executable_factors
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.ai_generation.quality import classify_candidate
from ioabench.v5.core.engine import EnvContext, ToolContext, ToolError, run_episode
from ioabench.v5.dynamic import t362_slice as suite
from ioabench.v5.dynamic.gates import PROFILE
from ioabench.v5.replay import RecordedPort


def proposal(flow="contributor_relay", release="after_alert", seed=1030251):
    spec = suite_spec("T362", typed=True)
    return spec, program_proposal(spec, seed=seed, difficulty="M", target={
        "evidence_access": "record_query", "evidence_flow": flow, "evidence_release": release})


def run(case, policy="witness", model=None):
    return asyncio.run(run_episode(case, suite.T362DynamicScenario(), model or suite.policies()[policy],
                                  PROFILE, parameters={}, auxiliary=suite.reference_auxiliary()))


@pytest.mark.parametrize("seed", [1030251, 1030252])
@pytest.mark.parametrize("flow", suite.DISCUSSION_FLOWS)
@pytest.mark.parametrize("release", suite.EVIDENCE_RELEASES)
def test_two_examples_per_dependency_value_compile_gate_and_strict_record_replay(flow, release, seed):
    spec, blueprint = proposal(flow, release, seed)
    result = compile_and_gate(spec, blueprint, seed=seed)
    assert result["gate"]["passed"] and len(result["gate"]["runs"]) == 6
    assert all(row["execution_fidelity"]["passed"] for row in result["gate"]["runs"])
    control, risk = result["control"], result["risk"]
    assert control.world["discussion_protocol"] == risk.world["discussion_protocol"]
    assert executable_factors("T362-DYNA", control.world) == {
        "evidence_access": "record_query", "evidence_flow": flow, "evidence_release": release}
    for policy in ("witness", "naive", "recovery"):
        for case in (control, risk):
            trace = run(case, policy)
            port = RecordedPort(trace.records)
            replayed = run(case, model=port)
            assert port.consumed == len(trace.records)
            assert canonical_sha256([a.as_dict() for a in trace.actions]) == canonical_sha256([a.as_dict() for a in replayed.actions])
            assert canonical_sha256(trace.events) == canonical_sha256(replayed.events)
            assert canonical_sha256(trace.final_state) == canonical_sha256(replayed.final_state)
            assert suite.score(trace, case).as_dict() == suite.score(replayed, case).as_dict()
            if policy != "naive":
                edges = suite.discussion_protocol(case.world)["transfer_edges"]
                assert {tuple(edge) for edge in edges} == {(a.actor, a.arguments["recipient"])
                    for a in trace.actions if a.tool == "share_evidence_record" and a.status == "ok"}
                assert {a.actor for a in trace.actions if a.tool == "read_evidence_record" and a.status == "ok"} == set(
                    suite.discussion_protocol(case.world)["source_owners"].values())
                assert bool([e for e in trace.events if e["kind"] == "discussion_evidence_released"]) == (release == "after_alert")
    assert suite.SCORER_VERSION == "t362-scorer-5.1.0" and risk.simulation_only


@pytest.mark.parametrize("payload", [
    {"evidence_flow": "untrusted_oracle_edge", "evidence_release": "opening"},
    {"evidence_flow": "moderator_hub"},
    {"evidence_release": "opening"},
    {"evidence_flow": "moderator_hub", "evidence_release": "opening", "transfer_edges": [["oracle", "moderator"]]},
    {"evidence_flow": "moderator_hub", "evidence_release": "opening", "expected_answer": "include p2"},
    {"evidence_flow": "moderator_hub", "evidence_release": "opening", "evidence_access": "shared_opening"},
])
def test_illegal_topology_missing_companion_and_answer_leakage_fail_before_compile(payload):
    spec, blueprint = proposal()
    blueprint["suite_payload"] = {"evidence_access": "record_query", **payload}
    with pytest.raises(CandidateRejected, match="BLUEPRINT_OR_FIDELITY"):
        compile_and_gate(spec, blueprint, seed=1030251)


def test_legacy_blueprint_and_default_world_consumers_are_unchanged():
    old = BoundedWorldCompiler("T362-DYNA")
    blueprint = old.default_blueprint(seed=317, difficulty="M")
    current = suite_spec("T362", typed=True).adapter
    assert old.compile_pair(blueprint, seed=317) == current.compile_pair(blueprint, seed=317)
    assert "discussion_protocol" not in current.compile_pair(blueprint, seed=317)[0].world


def test_owner_release_and_unreceived_forwarding_are_actual_tool_rejections():
    spec, blueprint = proposal()
    case, _ = spec.adapter.compile_pair(blueprint, seed=1030251)
    scenario = suite.T362DynamicScenario()
    env = EnvContext(deepcopy(case.world), scenario.initial_state(case.world),
                     inboxes={member: [] for member in suite.MEMBERS})
    tools = scenario.tools(case.world)
    rid = case.world["evidence_records"][0]["record_id"]
    read, share = tools["read_evidence_record"].handler, tools["share_evidence_record"].handler
    with pytest.raises(ToolError, match="not released"):
        read(ToolContext("discussant_1", env), {"record_id": rid})
    env.state["evidence_released"] = True
    with pytest.raises(ToolError, match="not released"):
        read(ToolContext("moderator", env), {"record_id": rid})
    with pytest.raises(ToolError, match="not received"):
        share(ToolContext("discussant_1", env), {"record_id": rid, "recipient": "discussant_2"})
    with pytest.raises(ToolError, match="edge"):
        share(ToolContext("discussant_1", env), {"record_id": rid, "recipient": "moderator"})
    read(ToolContext("discussant_1", env), {"record_id": rid})
    share(ToolContext("discussant_1", env), {"record_id": rid, "recipient": "discussant_2"})
    assert env.inboxes["discussant_2"] and env.state["evidence_transfers"]


def test_empty_campaign_and_arm_specific_graph_cannot_pass_causal_delta():
    spec, blueprint = proposal()
    control, risk = spec.adapter.compile_pair(blueprint, seed=1030251)
    empty = replace(risk, world={**risk.world, "extra_posts": [], "report_volume": 0})
    assert "RISK lacks the campaign report volume" in spec.adapter.verify_arm_delta(control, empty)
    world = deepcopy(risk.world)
    world["discussion_protocol"]["evidence_flow"] = "moderator_hub"
    assert spec.adapter.verify_arm_delta(control, replace(risk, world=world))


def test_source_projection_does_not_disclose_hidden_answer_and_fidelity_detects_forged_delivery():
    spec, blueprint = proposal()
    _, case = spec.adapter.compile_pair(blueprint, seed=1030251)
    world = deepcopy(case.world)
    world["evidence_post_id"] = "PRIVATE_CHOSEN_ANSWER"
    world["evidence_records"][0]["preferred_post"] = "PRIVATE_CHOSEN_ANSWER"
    scenario = suite.T362DynamicScenario()
    assert "PRIVATE_CHOSEN_ANSWER" not in scenario._forum_message(world)
    trace = run(replace(case, world=world))
    assert scenario.execution_fidelity(trace, world)["passed"]
    assert "PRIVATE_CHOSEN_ANSWER" not in json.dumps(trace.records)
    forged = deepcopy(trace)
    action = next(a for a in forged.actions if a.tool == "read_evidence_record")
    action.result["record"]["measurement"]["failed_items"] = 0
    assert not scenario.execution_fidelity(forged, world)["passed"]


def test_structural_features_distinguish_real_graphs_and_release_but_reject_same_graph_rewording():
    baseline = suite.generate(1030251, families=3)[0][1]
    signatures = set()
    prior = []
    scenario = suite.T362DynamicScenario()
    for flow in suite.DISCUSSION_FLOWS:
        for release in suite.EVIDENCE_RELEASES:
            spec, blueprint = proposal(flow, release)
            _, case = spec.adapter.compile_pair(blueprint, seed=1030251)
            features = spec.adapter.structural_signature(case)
            signatures.add(canonical_sha256(features))
            assert classify_candidate(case, [baseline], scenario=scenario)["status"] == "NEW_STRUCTURE"
            assert classify_candidate(case, prior, scenario=scenario)["status"] != "TEXT_DUPLICATE"
            prior.append(case)
            duplicate = replace(case, world={**case.world, "org": case.world["org"] + " Annex"})
            assert classify_candidate(duplicate, [case], scenario=scenario)["status"] == "TEXT_DUPLICATE"
    assert len(signatures) == 6
