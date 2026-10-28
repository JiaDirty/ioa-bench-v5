"""Inspect the registered factory boundary and execute bounded reference examples.

This is an implementation inventory, not a dataset or scientific acceptance gate.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import program_proposal, proposal_contract
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.core.case import SUITES
from ioabench.v5.dynamic.registry import implemented
from ioabench.v5.evaluation import atomic_json


def _tools(spec, case) -> dict[str, Any]:
    scenario = spec.scenario_factory()
    tools = scenario.tools(case.world)
    return {"scenario_version": scenario.version,
            "agents": [{"agent_id": agent.agent_id, "role": agent.role,
                        "tools": list(agent.tools)} for agent in scenario.agents(case.world)],
            "tools": {name: {"decision": tool.decision, "parameters": dict(tool.parameters),
                              "authority_scope": list(tool.authority_scope) if tool.authority_scope else None,
                              "audience_from_arg": tool.audience_from_arg}
                      for name, tool in sorted(tools.items())},
            "mechanism_slots": list(case.mechanism_slots),
            "oracle_keys": sorted(case.oracle),
            "simulation_only": case.simulation_only}


def _run(spec, blueprint, *, seed: int, execute: bool, require_execution_fidelity: bool = False) -> dict[str, Any]:
    result = {"adapter_version": spec.adapter.adapter_version, "blueprint": blueprint,
              "fidelity": "NOT_RUN", "deterministic_compilation": "NOT_RUN",
              "reference_gate": "NOT_RUN", "execution_fidelity": "NOT_RUN", "replay": "NOT_RUN"}
    try:
        findings = list(spec.adapter.validate_blueprint(blueprint))
        fidelity = dict(spec.adapter.fidelity_report(blueprint))
    except Exception as exc:
        return {**result, "status": "UNSUPPORTED", "findings": [
            {"stage": "VALIDATE", "exception": type(exc).__name__, "reason": str(exc)}]}
    result["fidelity"] = fidelity
    if findings or fidelity.get("gaps") or fidelity.get("faithful") is False:
        return {**result, "status": "UNSUPPORTED", "findings": [*findings, *fidelity.get("gaps", [])]}
    try:
        control, risk = spec.adapter.compile_pair(blueprint, seed=seed)
        pair = [control.as_dict(), risk.as_dict()]
        repeated = [case.as_dict() for case in spec.adapter.compile_pair(blueprint, seed=seed)]
        if pair != repeated:
            raise ValueError(f"non-deterministic capability example: {spec.suite_id}")
        result.update({"runtime": _tools(spec, control), "pair_sha256": canonical_sha256(pair),
                       "deterministic_compilation": "PASS", "pair": pair})
    except Exception as exc:
        return {**result, "status": "UNSUPPORTED", "findings": [
            {"stage": "COMPILE", "exception": type(exc).__name__, "reason": str(exc)}]}
    if not execute:
        return {**result, "status": "DECLARED_NOT_EXECUTED"}
    try:
        if require_execution_fidelity and not callable(getattr(spec.scenario_factory(), "execution_fidelity", None)):
            return {**result, "status": "UNSUPPORTED", "findings": [
                {"stage": "EXECUTION_FIDELITY", "reason": "scenario has no actual consumer-proof hook"}]}
        gated = compile_and_gate(spec, blueprint, seed=seed)
    except CandidateRejected as exc:
        return {**result, "status": "EXPERIMENTAL", "reference_gate": "FAIL",
                "rejection_stage": exc.stage, "findings": exc.findings}
    except Exception as exc:
        return {**result, "status": "EXPERIMENTAL", "reference_gate": "FAIL", "findings": [
            {"stage": "REFERENCE", "exception": type(exc).__name__, "reason": str(exc)}]}
    gate = gated["gate"]
    runs = gate.get("runs", [])
    expected_runs = {(getattr(model, "name", "?"), arm) for model in spec.policies.values()
                     for arm in ("CONTROL", "RISK")}
    actual_runs = {(run.get("policy"), run.get("arm")) for run in runs}
    if (gate.get("passed") is not True or not expected_runs or actual_runs != expected_runs
            or len(runs) != len(expected_runs) or any(run.get("status") != "COMPLETED" for run in runs)):
        return {**result, "status": "EXPERIMENTAL", "reference_gate": "FAIL", "gate": gate,
                "findings": [{"stage": "REFERENCE", "reason": "missing, incomplete or failed executed reference gate"}]}
    fidelity_passed = bool(runs) and all(run.get("execution_fidelity", {}).get("passed") is True for run in runs)
    if require_execution_fidelity and not fidelity_passed:
        return {**result, "status": "EXPERIMENTAL", "reference_gate": "FAIL", "gate": gated["gate"],
                "execution_fidelity": "FAIL", "findings": [{"stage": "EXECUTION_FIDELITY",
                "reason": "not every actual reference run supplied a passing consumer proof"}]}
    return {**result, "status": "SUPPORTED", "reference_gate": "PASS", "gate": gated["gate"],
            "execution_fidelity": "PASS" if fidelity_passed else "NOT_APPLICABLE"}


def _typed(spec, *, seed: int, execute: bool) -> dict[str, Any]:
    try:
        context = (spec.adapter.generator_context(seed=seed) if hasattr(spec.adapter, "generator_context")
                   else proposal_contract(spec, seed=seed, difficulty="M"))
        difficulty = context["example_blueprint"]["difficulty"]
        constraints = proposal_contract(spec, seed=seed, difficulty=difficulty)
        blueprint = program_proposal(spec, seed=seed, difficulty=difficulty)
        schema = constraints["schema"]["properties"]["suite_payload"]
    except Exception as exc:
        return {"adapter_version": spec.adapter.adapter_version, "status": "UNSUPPORTED",
                "structural_acquisition": "UNSUPPORTED", "reference_gate": "NOT_RUN",
                "execution_fidelity": "NOT_RUN", "replay": "NOT_RUN", "finite_executable_factors": {},
                "factor_examples": [], "verified_new_families": 0, "findings": [
                    {"stage": "PROGRAM_PROPOSAL", "exception": type(exc).__name__, "reason": str(exc)}]}
    factors = {name: {"path": "/suite_payload/" + name, "values": value["enum"]}
               for name, value in schema.get("properties", {}).items()
               if "enum" in value and len(value["enum"]) > 1}
    unsupported = deepcopy(blueprint)
    unsupported["suite_payload"]["unsupported_factory_capability"] = True
    try:
        rejected = list(spec.adapter.validate_blueprint(unsupported))
    except Exception as exc:
        rejected = []
        control_findings = [{"stage": "UNSUPPORTED_FIELD_CONTROL", "exception": type(exc).__name__, "reason": str(exc)}]
    else:
        control_findings = rejected or [{"stage": "UNSUPPORTED_FIELD_CONTROL", "reason": "typed schema accepted an undeclared field"}]
    field_control = {"status": "REJECTED" if rejected else "FAIL", "findings": control_findings,
                     "proposal_sha256": canonical_sha256(unsupported), "provider_calls": 0}
    if not rejected:
        return {"adapter_version": spec.adapter.adapter_version, "status": "UNSUPPORTED",
                "structural_acquisition": "UNSUPPORTED", "reference_gate": "NOT_RUN",
                "execution_fidelity": "NOT_RUN", "replay": "NOT_RUN", "finite_executable_factors": factors,
                "factor_examples": [], "verified_new_families": 0, "unsupported_field_control": field_control,
                "findings": control_findings}
    executed = _run(spec, blueprint, seed=seed, execute=execute, require_execution_fidelity=True)
    examples = []
    names = sorted(factors)
    for values in product(*(factors[name]["values"] for name in names)) if names else ():
        target = dict(zip(names, values))
        try:
            proposed = program_proposal(spec, seed=seed, difficulty=difficulty, target=target)
        except Exception as exc:
            example = {"status": "UNSUPPORTED", "reference_gate": "NOT_RUN", "execution_fidelity": "NOT_RUN",
                       "replay": "NOT_RUN", "findings": [{"stage": "PROGRAM_PROPOSAL",
                       "exception": type(exc).__name__, "reason": str(exc)}]}
        else:
            example = _run(spec, proposed, seed=seed, execute=execute, require_execution_fidelity=True)
        examples.append({"factors": target, **example})
    supported = [row for row in examples if row["status"] == "SUPPORTED"]
    declared = any(row["status"] == "DECLARED_NOT_EXECUTED" for row in examples)
    return {**executed, "finite_executable_factors": factors, "factor_examples": examples,
            "factor_status_counts": {status: sum(row["status"] == status for row in examples)
                for status in sorted({row["status"] for row in examples})},
            "structural_acquisition": ("SUPPORTED" if supported else
                "DECLARED_NOT_EXECUTED" if declared else "UNSUPPORTED"),
            "scope": "Bounded declared compiler factors only; no claim for arbitrary graphs or new primitives.",
            "constraints_sha256": canonical_sha256(constraints),
            "unsupported_field_control": field_control,
            "independent_review": "NOT_RUN", "empirical_difficulty": "NOT_RUN",
            "global_behavioral_novelty": "NOT_RUN", "verified_new_families": 0}


def build_manifest(*, execute: bool = True, seed: int = 6101900) -> dict[str, Any]:
    before = source_tree_hash(ROOT)
    slices, suites = {}, {}
    for offset, slice_id in enumerate(implemented()):
        spec = suite_spec(slice_id)
        blueprint = spec.adapter.default_blueprint(seed=seed + offset)
        record = _run(spec, blueprint, seed=seed + offset, execute=execute)
        record["scope"] = "Existing registered dynamic structure with neutral narrative enrichment."
        record["structural_acquisition"] = "UNSUPPORTED"
        slices[slice_id] = record
    for offset, suite in enumerate(SUITES):
        suite_slices = [slice_id for slice_id in slices if slice_id.startswith(suite + "-")]
        try:
            typed_spec = suite_spec(suite, typed=True)
        except ValueError as exc:
            typed = {"registered": False, "status": "UNSUPPORTED", "structural_acquisition": "UNSUPPORTED",
                     "reason": str(exc), "reference_gate": "NOT_RUN",
                     "execution_fidelity": "NOT_RUN", "replay": "NOT_RUN",
                     "finite_executable_factors": {}, "verified_new_families": 0}
        else:
            typed = _typed(typed_spec, seed=seed + 100 + offset, execute=execute)
            typed["registered"] = True
        suites[suite] = {"dynamic_slices": suite_slices,
            "runtime_reference_status": "SUPPORTED" if suite_slices and all(slices[s]["reference_gate"] == "PASS" for s in suite_slices)
                else "NOT_RUN" if not execute else "EXPERIMENTAL",
            "typed_compiler": typed, "simulation_only": suite in {"T361", "T362", "T363"},
            "dataset_status": "EXPERIMENTAL", "formal_accepted": False}
    if source_tree_hash(ROOT) != before:
        raise ValueError("runtime source changed during capability inspection; rerun under the writer lock")
    typed_rows = [suite["typed_compiler"] for suite in suites.values()]
    report = {"schema_version": "ioabench.v5.factory-capability-manifest/1.1.0",
        "runtime_source_sha256": before, "seed": seed, "suites": suites, "slices": slices,
        "suite_count": len(suites), "slice_count": len(slices), "provider_calls": 0,
        "typed_registered_suite_count": sum(row["registered"] for row in typed_rows),
        "typed_supported_suite_count": sum(row["structural_acquisition"] == "SUPPORTED" for row in typed_rows),
        "reference_gate_executions": sum(len(row.get("gate", {}).get("runs", []))
            for row in [*slices.values(), *typed_rows, *(example for row in typed_rows for example in row.get("factor_examples", []))]),
        "source_sha256": {Path(__file__).relative_to(ROOT).as_posix(): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "scope": "One default example per registered slice plus all finite enum cells in each seed-bound typed grammar; not all subtypes, arbitrary graphs or scientific qualification.",
        "scientific_validity": "NOT_ESTABLISHED", "formal_frozen": False,
        "independent_review": "NOT_RUN", "empirical_difficulty": "NOT_RUN", "replay": "NOT_RUN"}
    report = json.loads(json.dumps(report, allow_nan=False))
    report["manifest_sha256"] = canonical_sha256(report)
    return report


def write_manifest(path: Path, report: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != report:
            raise ValueError("immutable capability manifest differs; use a new output path")
        return
    atomic_json(path, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=6101900)
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    from routed_t321_data_factory_s1 import _lock
    with _lock(ROOT / "artifacts/v5/overnight_runs/.writer.lock"):
        report = build_manifest(execute=not args.inspect_only, seed=args.seed)
        write_manifest(args.output, report)
    print(json.dumps({"output": str(args.output.resolve()), "suite_count": report["suite_count"],
        "slice_count": report["slice_count"], "reference_gate_executions": report["reference_gate_executions"],
        "provider_calls": 0, "manifest_sha256": report["manifest_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
