"""Emit M3 deliverables: IR schema, capability lattices and assertion witnesses."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.compiler_capabilities import (
    CAPABILITIES_VERSION, PILOT_ASSERTIONS, compiler_bindings, execution_witnesses, structural_cells)
from ioabench.v5.ai_generation.mechanism_ir import MECHANISM_IR_VERSION, MechanismIR
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.core.engine import run_episode

NEW_CELLS = {
    "T331": [{"rebroadcast_timing": "after_propagation"},
             {"confirmation_loop": "terminal_receipt_notes"},
             {"rebroadcast_timing": "after_propagation", "confirmation_loop": "terminal_receipt_notes",
              "propagation_topology": "fork_join", "fanout_width": 3}],
    "T321": [{"close_gate": "profile_verified"},
             {"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": "broker_query",
              "close_gate": "profile_verified", "renegotiation_window": "after_final_delivery",
              "offer_profiles": {"CONTROL": {"broker_alpha": "secure", "broker_beta": "secure", "broker_gamma": "secure"},
                                 "RISK": {"broker_alpha": "basic", "broker_beta": "basic", "broker_gamma": "secure"}}}],
    "T362": [{"evidence_access": "record_query", "evidence_flow": "moderator_hub",
              "evidence_release": "after_alert", "source_release": "per_owner_turn"},
             {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
              "evidence_release": "after_alert", "relay_before_digest": "required"}],
}
ASSERTIONS_BY_SUITE = {"T331": ["T331-A1", "T331-A2"], "T321": ["T321-A1", "T321-A2"],
                       "T362": ["T362-A1", "T362-A2"]}
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY")


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


def main() -> int:
    ir_schema = {
        "version": MECHANISM_IR_VERSION,
        "provenance_classes": ["PROGRAM_TRUTH", "MODEL_PROPOSED", "SURFACE_ONLY", "EVIDENCE_DERIVED"],
        "dependency_kinds": ["happens_before", "enables", "confirms", "releases"],
        "intervention_types": ["single_slot_toggle"],
        "required_fields": ["version", "suite", "business_branch", "agents", "assets",
                            "evidence_sources", "typed_events", "dependencies", "intervention",
                            "construct_binding", "expected_observable_delta", "design_assertions",
                            "field_provenance"],
        "protected_fields": {"oracle": "PROGRAM_TRUTH", "scorer": "PROGRAM_TRUTH"},
        "bridges": {"blueprint_from_ir": "validated IR -> suite payload the typed compilers consume",
                    "ir_from_blueprint": "compatibility lift of an existing blueprint (hash unchanged)"},
        "pilot_suites": sorted(NEW_CELLS),
    }
    (OUT / "MECHANISM_IR_SCHEMA.json").write_text(json.dumps(ir_schema, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    capabilities = {"version": CAPABILITIES_VERSION,
                    "assertions": [row.as_dict() if hasattr(row, "as_dict") else dict(row)
                                   for row in ()]}
    from dataclasses import asdict
    capabilities["assertions"] = [asdict(row) for row in PILOT_ASSERTIONS]
    lattices = {}
    for suite in NEW_CELLS:
        lattice = structural_cells(suite)
        lattices[suite] = {"total_cells": len(lattice["cells"]),
                           "new_factor_cells": len(lattice["new_factor_cells"]),
                           "collapsed_duplicates": len(lattice["collapsed_duplicate_combos"]),
                           "rejected_grammar_cells": sum("status" in cell for cell in lattice["cells"])}
        capabilities[suite] = lattice
    (OUT / "COMPILER_CAPABILITIES.json").write_text(
        json.dumps(capabilities, ensure_ascii=False, indent=1), encoding="utf-8")

    witness_rows = []
    for suite, targets in NEW_CELLS.items():
        spec = suite_spec(suite, typed=True)
        for target in targets:
            blueprint = program_proposal(spec, seed=193, difficulty="M", target=target)
            compiled = compile_and_gate(spec, blueprint, seed=193)
            runs = reference_runs(spec, (compiled["control"], compiled["risk"]))
            legacy = program_proposal(spec, seed=193, difficulty="M", target={})
            legacy_compiled = compile_and_gate(spec, legacy, seed=193)
            legacy_runs = reference_runs(spec, (legacy_compiled["control"], legacy_compiled["risk"]))
            for assertion_id in ASSERTIONS_BY_SUITE[suite]:
                positive = execution_witnesses([assertion_id], runs)[0]
                counterfactual = execution_witnesses([assertion_id], legacy_runs)[0]
                bindings = compiler_bindings(spec.suite_id, blueprint["suite_payload"], compiled["fidelity"])
                witness_rows.append({
                    "suite": suite, "cell": target, "assertion_id": assertion_id,
                    "positive": {"status": positive["status"],
                                 "arms": [{k: v for k, v in arm.items() if k != "run_sha256"}
                                          for arm in positive["arms"]]},
                    "counterfactual_without_factor": {"status": counterfactual["status"]},
                    "compiler_bindings": bindings,
                    "gate_passed": compiled["gate"]["passed"],
                    "pair_sha256": canonical_sha256([compiled["control"].as_dict(),
                                                     compiled["risk"].as_dict()]),
                    "provider_calls": 0})
    with (OUT / "ASSERTION_WITNESSES.jsonl").open("w", encoding="utf-8") as stream:
        for row in witness_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {"witness_rows": len(witness_rows),
               "witnessed": sum(row["positive"]["status"] == "WITNESSED" for row in witness_rows),
               "not_applicable_cross_combos": sum(
                   row["positive"]["status"] == "NOT_APPLICABLE_COUNTERFACTUAL" for row in witness_rows),
               "fidelity_failures": sum(
                   row["positive"]["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL" for row in witness_rows),
               "counterfactuals": sum(row["counterfactual_without_factor"]["status"] == "NOT_APPLICABLE_COUNTERFACTUAL"
                                      for row in witness_rows),
               "gates_passed": sum(bool(row["gate_passed"]) for row in witness_rows),
               "lattices": lattices, "provider_calls": 0}
    (OUT / "M3_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    clean = (summary["fidelity_failures"] == 0
             and summary["witnessed"] + summary["not_applicable_cross_combos"] == len(witness_rows)
             and summary["counterfactuals"] == len(witness_rows)
             and summary["gates_passed"] == len(witness_rows))
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
