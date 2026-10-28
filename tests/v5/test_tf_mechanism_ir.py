"""MechanismIR, compiler capabilities and design-assertion execution witnesses (M3)."""
from __future__ import annotations

import asyncio

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.compiler_capabilities import (
    PILOT_ASSERTIONS, compiler_bindings, execution_witnesses, structural_cells)
from ioabench.v5.ai_generation.mechanism_ir import (
    IRAgent, IRAsset, IRAssertion, IRDependency, IREvent, IREvidence, IRIntervention,
    MECHANISM_IR_VERSION, MechanismIR, blueprint_from_ir, ir_from_blueprint)
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.core.engine import run_episode

NEW_CELLS = {
    "T331": [{"rebroadcast_timing": "after_propagation"},
             {"confirmation_loop": "terminal_receipt_notes"}],
    "T321": [{"close_gate": "profile_verified", "offer_profiles": None},
             {"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": "broker_query",
              "close_gate": "profile_verified", "renegotiation_window": "after_final_delivery",
              "offer_profiles": {"CONTROL": {"broker_alpha": "secure", "broker_beta": "secure", "broker_gamma": "secure"},
                                 "RISK": {"broker_alpha": "basic", "broker_beta": "basic", "broker_gamma": "secure"}}}],
    "T362": [{"evidence_access": "record_query", "evidence_flow": "moderator_hub",
              "evidence_release": "after_alert", "source_release": "per_owner_turn"},
             # relay gate is moderator_hub-only: other flows give the moderator no
             # outgoing edge, which the compiler rejects as a structural deadlock
             {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
              "evidence_release": "after_alert", "relay_before_digest": "required"}],
}
ASSERTION_BY_CELL = {
    ("T331", "rebroadcast_timing"): "T331-A1",
    ("T331", "confirmation_loop"): "T331-A2",
    ("T321", "close_gate"): "T321-A1",
    ("T321", "renegotiation_window"): "T321-A2",
    ("T362", "source_release"): "T362-A1",
    ("T362", "relay_before_digest"): "T362-A2",
}
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY")


def blueprint_for(suite, target):
    spec = suite_spec(suite, typed=True)
    from ioabench.v5.ai_generation.acquisition import program_proposal
    clean = {key: value for key, value in target.items() if value is not None}
    return program_proposal(spec, seed=193, difficulty="M", target=clean), spec


def reference_runs(spec, pair):
    scenario = spec.scenario_factory()
    runs = []
    for policy_name, model in spec.policies.items():
        for case in pair:
            trace = asyncio.run(run_episode(case, scenario, model, PROFILE,
                                            parameters={"temperature": 0.0}))
            runs.append({"arm": case.arm, "policy": policy_name, "trace": trace,
                         "world": dict(case.world)})
    return runs


def test_ir_validation_rejects_cycles_unknown_endpoints_and_empty_interventions():
    agents = (IRAgent("a", "operator", ("t",)),)
    events = (IREvent("e1", "a", "submit"), IREvent("e2", "a", "confirm"))
    bad_cycle = MechanismIR(MECHANISM_IR_VERSION, "T331", "x", agents, (), (), events,
                            (IRDependency("e1", "e2", "happens_before"),
                             IRDependency("e2", "e1", "happens_before")),
                            IRIntervention("/slot", "c", "r"), "T331", ("/slot",), ())
    assert "DEPENDENCY_CYCLE" in bad_cycle.validate()
    bad_endpoint = MechanismIR(MECHANISM_IR_VERSION, "T331", "x", agents, (), (),
                               (IREvent("e1", "a", "submit"),),
                               (IRDependency("e1", "missing", "enables"),),
                               IRIntervention("/slot", "c", "r"), "T331", ("/slot",), ())
    assert any(error.startswith("DEPENDENCY_ENDPOINT_UNKNOWN") for error in bad_endpoint.validate())
    no_effect = MechanismIR(MECHANISM_IR_VERSION, "T331", "x", agents, (), (), events, (),
                            IRIntervention("/slot", "same", "same"), "T331", ("/slot",), ())
    assert "INTERVENTION_HAS_NO_EFFECT" in no_effect.validate()
    bad_provenance = MechanismIR(MECHANISM_IR_VERSION, "T331", "x", agents, (), (), events, (),
                                 IRIntervention("/slot", "c", "r"), "T331", ("/slot",), (),
                                 field_provenance={"oracle": "MODEL_PROPOSED"})
    assert "PROTECTED_FIELD_NOT_PROGRAM_OWNED:oracle" in bad_provenance.validate()
    ok = MechanismIR(MECHANISM_IR_VERSION, "T331", "x", agents,
                     (IRAsset("rec", "record", "a"),), (IREvidence("ev", "receipt", ("a",)),),
                     (IREvent("e1", "a", "submit", (), ("rec",)), IREvent("e2", "a", "confirm", ("e1",), ("ev",))),
                     (IRDependency("e1", "e2", "happens_before"),),
                     IRIntervention("/slot", "c", "r"), "T331", ("/slot",),
                     (IRAssertion("a1", "receipt before clearance", ("/typed_events/1",)),),
                     field_provenance={"oracle": "PROGRAM_TRUTH"})
    assert ok.validate() == []


def test_ir_to_blueprint_roundtrip_compiles_and_gates_for_every_new_cell():
    for suite, targets in NEW_CELLS.items():
        for target in targets:
            blueprint, spec = blueprint_for(suite, target)
            # R2 fail-closed contract: the IR must carry the real compiled agents
            # (ir_from_blueprint lifts them); an empty-agent IR can no longer project.
            ir = ir_from_blueprint(spec.suite_id, blueprint)
            assert ir.validate() == []
            projected = blueprint_from_ir(ir)
            compiled = compile_and_gate(spec, projected, seed=193)
            assert compiled["gate"]["passed"], (suite, target, compiled["gate"]["failures"])


def test_legacy_blueprint_lifts_into_ir_without_mutation():
    blueprint, spec = blueprint_for("T331", {})
    digest = canonical_sha256(blueprint)
    ir = ir_from_blueprint("T331", blueprint)
    assert canonical_sha256(blueprint) == digest
    assert ir.validate() == [] or "AGENTS_INVALID" not in ir.validate()
    assert ir.field_provenance["oracle"] == "PROGRAM_TRUTH"
    assert ir.intervention.slot_id == "/mid_episode_update/value"


@pytest.mark.parametrize("suite,key,assertion_id", sorted(
    [(suite, key, aid) for (suite, key), aid in ASSERTION_BY_CELL.items()]),
    ids=lambda value: str(value))
def test_design_assertions_have_positive_execution_witnesses(suite, key, assertion_id):
    targets = next(target for target in NEW_CELLS[suite] if key in target)
    blueprint, spec = blueprint_for(suite, targets)
    compiled = compile_and_gate(spec, blueprint, seed=193)
    runs = reference_runs(spec, (compiled["control"], compiled["risk"]))
    rows = execution_witnesses([assertion_id], runs)
    assert rows[0]["status"] == "WITNESSED", rows[0]
    # counterfactual: same suite compiled WITHOUT the factor must not satisfy the witness
    legacy, legacy_spec = blueprint_for(suite, {})
    legacy_compiled = compile_and_gate(legacy_spec, legacy, seed=193)
    legacy_runs = reference_runs(legacy_spec, (legacy_compiled["control"], legacy_compiled["risk"]))
    counterfactual = execution_witnesses([assertion_id], legacy_runs)
    assert counterfactual[0]["status"] == "NOT_APPLICABLE_COUNTERFACTUAL", counterfactual[0]


@pytest.mark.parametrize("suite,key,assertion_id", sorted(
    [(suite, key, aid) for (suite, key), aid in ASSERTION_BY_CELL.items()]),
    ids=lambda value: str(value))
def test_new_factors_map_to_compiler_bindings(suite, key, assertion_id):
    targets = next(target for target in NEW_CELLS[suite] if key in target)
    blueprint, spec = blueprint_for(suite, targets)
    compiled = compile_and_gate(spec, blueprint, seed=193)
    bindings = compiler_bindings(spec.suite_id, blueprint["suite_payload"], compiled["fidelity"])
    binding = next(row for row in bindings if row["factor"] == key)
    assert binding["status"] == "MAPPED" and binding["consumer"], binding
    unknown = compiler_bindings(spec.suite_id, {"not_a_factor": "x"}, compiled["fidelity"])
    assert unknown[0]["status"] == "CAPABILITY_GAP"


def test_renaming_and_domain_changes_do_not_create_new_structure():
    blueprint, spec = blueprint_for("T331", {"rebroadcast_timing": "after_propagation"})
    renamed = {**blueprint, "suite_payload": {**blueprint["suite_payload"],
                                              "organization": "Riverside Partners"}}
    base = compile_and_gate(spec, blueprint, seed=193)
    variant = compile_and_gate(spec, renamed, seed=193)
    assert canonical_sha256(spec.adapter.structural_signature(base["control"])) == \
           canonical_sha256(spec.adapter.structural_signature(variant["control"]))
    changed, _ = blueprint_for("T331", {"confirmation_loop": "terminal_receipt_notes",
                                        "rebroadcast_timing": "after_propagation"})
    other = compile_and_gate(spec, changed, seed=193)
    assert canonical_sha256(spec.adapter.structural_signature(base["control"])) != \
           canonical_sha256(spec.adapter.structural_signature(other["control"]))


@pytest.mark.parametrize("suite", ["T331", "T321", "T362"])
def test_structural_cell_lattice_extends_beyond_legacy_cells(suite):
    lattice = structural_cells(suite)
    digests = {cell["signature_digest"] for cell in lattice["cells"] if "signature_digest" in cell}
    legacy = {cell["signature_digest"] for cell in lattice["cells"]
              if cell.get("legacy_factors_only") and "signature_digest" in cell}
    fresh = {cell["signature_digest"] for cell in lattice["new_factor_cells"]
             if "signature_digest" in cell}
    assert len(digests) == len([cell for cell in lattice["cells"] if "signature_digest" in cell])
    assert fresh and fresh.isdisjoint(legacy)
    assert len(fresh) >= 2, "each pilot must expose at least two new-structure cells"


def test_all_pilot_assertions_are_registered_with_predicates():
    from ioabench.v5.ai_generation.compiler_capabilities import WITNESS_PREDICATES
    assert {item.assertion_id for item in PILOT_ASSERTIONS} == set(WITNESS_PREDICATES)
    assert len(PILOT_ASSERTIONS) == 19


def test_t362_relay_gate_with_edgeless_moderator_flow_fails_closed():
    from ioabench.v5.ai_generation.pipeline import CandidateRejected
    # split_sources gives the moderator no outgoing transfer edge; the relay gate
    # cannot be satisfied there and the compiler grammar rejects the combination.
    with pytest.raises(CandidateRejected):
        blueprint_for("T362", {"evidence_access": "record_query",
                               "evidence_flow": "split_sources",
                               "evidence_release": "after_alert",
                               "relay_before_digest": "required"})
