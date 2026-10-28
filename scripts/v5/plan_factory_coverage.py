"""Plan compiler-constrained structural coverage and execute the selected reference gates."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.generation.coverage import CoveragePlanner
from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.bounded_compiler import FACTORS
from ioabench.v5.core.case import SUITES
from ioabench.v5.evaluation import atomic_json

SUBTYPES = {"T321": "T321-S5", "T331": "T331-S5", "T352": "T352-S1"}


def _spec(suite):
    if suite != "T321":
        return suite_spec(suite, typed=True)
    from ioabench.v5.ai_generation.t321_dyna_compiler import T321DynaCompiler
    return replace(suite_spec(suite), adapter=T321DynaCompiler())


def _constraints(spec):
    if hasattr(spec.adapter, "generator_context"):
        return spec.adapter.generator_context(seed=0, difficulty="M")
    if spec.suite_id == "T312-DYNA":
        return spec.adapter.generator_constraints(subtype="T312-S2", difficulty="M")
    return spec.adapter.generator_constraints(subtype=SUBTYPES[spec.suite_id.split("-")[0]], difficulty="M")


def _factors(suite, constraints):
    if suite + "-DYNA" in FACTORS:
        field, values, _ = FACTORS[suite + "-DYNA"]
        return {field: list(values)}
    if suite == "T312":
        return {"operational_evidence": list(constraints["schema"]["properties"]["suite_payload"]["properties"]["operational_evidence"]["enum"])}
    if suite == "T321":
        return {"broker_count": [2, 3], "peer_profile_delivery": ["initial", "broker_gamma"],
                "offer_access": ["scheduled_push", "broker_query"]}
    properties = constraints["schema"]["properties"]["suite_payload"]["properties"]
    names = ("fanout_width", "propagation_topology") if suite == "T331" else ("allocator_count", "report_access", "reputation_governance")
    return {name: list(properties[name]["enum"]) for name in names}


def _blueprint(spec, constraints, row, difficulty):
    if "example_blueprint" in constraints:
        blueprint = deepcopy(constraints["example_blueprint"])
    elif hasattr(spec.adapter, "default_blueprint"):
        blueprint = deepcopy(spec.adapter.default_blueprint(seed=0))
    elif spec.suite_id == "T321-DYNA":
        blueprint = json.loads((ROOT / "contracts/v5/generation_seeds/T321-S5.json").read_text(encoding="utf-8"))
    else:
        raise ValueError("CAPABILITY_GAP: compiler has no production default_blueprint/example_blueprint")
    blueprint["difficulty"] = difficulty
    blueprint["suite_payload"].update(row)
    if spec.suite_id == "T321-DYNA":
        brokers = ["broker_alpha", "broker_beta"] + (["broker_gamma"] if row["broker_count"] == 3 else [])
        blueprint["suite_payload"]["offer_profiles"] = {
            arm: {broker: constraints["required_offer_profiles"][arm][broker] for broker in brokers}
            for arm in ("CONTROL", "RISK")}
    return blueprint


def run(output: Path):
    source_hash = source_tree_hash(ROOT)
    reports, cases = {}, []
    for suite in SUITES:
        spec = _spec(suite)
        constraints = _constraints(spec)
        factors = _factors(suite, constraints)
        try:
            def feasible(row):
                try:
                    blueprint = program_proposal(spec, seed=0, difficulty="M", target=row)
                    return not spec.adapter.validate_blueprint(blueprint) and not spec.adapter.fidelity_report(blueprint).get("gaps")
                except CandidateRejected:
                    return False
            plan = CoveragePlanner().plan_factors(factors, feasible=feasible)
        except (KeyError, TypeError, ValueError) as exc:
            reports[suite] = {"status": "UNSUPPORTED", "tested": "NOT_RUN", "code": "CAPABILITY_GAP",
                              "reason": str(exc), "factors": factors, "qualified_families": 0}
            continue
        rows = []
        for row in plan["selected_rows"]:
            for difficulty in ("E", "M", "H"):
                seed = 6101900 + len(cases)
                try:
                    blueprint = program_proposal(spec, seed=seed, difficulty=difficulty, target=row)
                    result = compile_and_gate(spec, blueprint, seed=seed)
                    repeated = spec.adapter.compile_pair(blueprint, seed=seed)
                    pair = [result["control"].as_dict(), result["risk"].as_dict()]
                    if pair != [case.as_dict() for case in repeated]:
                        raise ValueError("same proposal and seed failed deterministic compilation")
                    cases.extend(pair)
                    rows.append({"factors": row, "difficulty_target": difficulty, "seed": seed,
                                 "status": "REFERENCE_GATE_PASS", "blueprint": blueprint,
                                 "pair_sha256": canonical_sha256(pair), "fidelity": result["fidelity"],
                                 "gate": result["gate"], "difficulty_empirical": "NOT_RUN"})
                except (CandidateRejected, ValueError) as exc:
                    rows.append({"factors": row, "difficulty_target": difficulty, "seed": seed,
                                 "status": "REJECTED", "reason": str(exc),
                                 "findings": getattr(exc, "findings", [])})
        reports[suite] = {"status": "SUPPORTED" if all(row["status"] == "REFERENCE_GATE_PASS" for row in rows) else "EXPERIMENTAL",
                         "scope": "Declared bounded compiler factors only", "plan": plan,
                         "executions": rows, "qualified_families": 0, "qualified_instances": 0,
                         "difficulty_empirical": "NOT_RUN", "independent_machine_review": "NOT_RUN"}
    if source_tree_hash(ROOT) != source_hash:
        raise ValueError("runtime source changed during coverage execution; use a new output directory")
    report = {"schema_version": "ioabench.v5.compiler-coverage/1.0.0", "suites": reports,
              "runtime_source_sha256": source_hash,
              "provider_calls": 0, "formal_accepted": False, "sampling": "EXPLORATORY_ACQUISITION_ONLY",
              "reference_gate_checks": sum(len(row.get("gate", {}).get("runs", []))
                                           for suite in reports.values() for row in suite.get("executions", [])),
              "case_count": len(cases), "source_sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in [Path(__file__), ROOT / "src/ioabench/generation/coverage.py"]}}
    for name, value in (("COVERAGE.json", report), ("PAIRS.json", cases)):
        path = output / name
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != value:
                raise ValueError("immutable coverage output changed; use a new output directory")
        else:
            atomic_json(path, value)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "case_count": report["case_count"],
                      "reference_gate_checks": report["reference_gate_checks"],
                      "statuses": {suite: row["status"] for suite, row in report["suites"].items()}}, ensure_ascii=False))
    raise SystemExit(0 if all(row["status"] == "SUPPORTED" for row in report["suites"].values()) else 1)
