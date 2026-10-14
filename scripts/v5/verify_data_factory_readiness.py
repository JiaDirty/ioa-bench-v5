"""Offline acceptance of compiler fidelity; historical candidates remain read-only.

This diagnoses readiness, not scientific acceptance. Any unexpected acceptance of a
known unsupported proposal is a failed quality check and requires a PI notification.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.v5.ai_generation.t321_dyna_compiler import T321DynaCompiler  # noqa: E402
from ioabench.v5.dynamic import t321_slice  # noqa: E402
from ioabench.v5.dynamic.gates import check_pair_dynamic  # noqa: E402


def verify(blueprint):
    compiler = T321DynaCompiler()
    findings = compiler.validate_blueprint(blueprint)
    fidelity = compiler.fidelity_report(blueprint)
    checks = [{"name": "original_blueprint_compiles", "passed": not findings and not fidelity["gaps"],
               "schema_findings": findings, "fidelity": fidelity}]
    if not checks[0]["passed"]:
        return checks
    control, risk = compiler.compile_pair(blueprint, seed=11)
    gate = check_pair_dynamic(control, risk, scenario=t321_slice.T321DynamicAScenario(),
                             scorer=t321_slice.score, policies=t321_slice.policies(),
                             expected=t321_slice.EXPECTED_REFERENCE, fine_arm_delta=t321_slice.fine_arm_delta)
    checks.append({"name": "original_pair_reference_gates", "passed": gate["passed"], "report": gate})
    if not gate["passed"]:
        return checks

    duplicate = deepcopy(blueprint)
    duplicate["task_graph"].append(deepcopy(duplicate["task_graph"][-1]))
    missing_evidence = deepcopy(blueprint)
    missing_evidence["task_graph"][0]["evidence_refs"].append("never_supplied_evidence")
    unsupported_requirement = deepcopy(blueprint)
    unsupported_requirement["world_concept"]["business_constraints"].append(
        "A manager must approve every transfer using the approve_manager tool before send_data.")
    unknown_source = deepcopy(blueprint)
    unknown_source["evidence_plan"][0]["source"] = "external public Internet authority requiring network lookup"
    for name, altered in (("duplicate_task_node_rejected", duplicate),
                          ("missing_evidence_reference_rejected", missing_evidence),
                          ("unsupported_required_approval_rejected", unsupported_requirement),
                          ("unsupported_evidence_source_rejected", unknown_source)):
        findings = compiler.validate_blueprint(altered)
        fidelity = compiler.fidelity_report(altered)
        blocked = bool(findings or fidelity["gaps"])
        check = {"name": name, "passed": blocked, "expected": "reject before compilation",
                 "schema_findings": findings, "fidelity": fidelity, "mutated_blueprint": altered}
        if not blocked:
            actual_control, actual_risk = compiler.compile_pair(altered, seed=11)
            check["actual"] = "invalid proposal compiled without a capability gap"
            check["compiled_case_hashes"] = [canonical_sha256(case.as_dict()) for case in (actual_control, actual_risk)]
        checks.append(check)
        if not blocked:
            break
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; choose a new evidence path")
    original = args.candidate.read_bytes()
    candidate = json.loads(original)
    blueprint = candidate["blueprint"]
    checks = verify(blueprint)
    report = {"schema": "ioabench.v5.data-factory-readiness/1", "evidence_class": "ENGINEERING_NEGATIVE_CONTROLS",
              "compiler": T321DynaCompiler.adapter_version, "source": args.candidate.as_posix(),
              "blueprint_sha256": canonical_sha256(blueprint), "checks": checks,
              "passed": all(check["passed"] for check in checks), "provider_calls": 0,
              "source_unchanged": args.candidate.read_bytes() == original, "publication_ready": False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    for check in checks:
        print(f"{'PASS' if check['passed'] else 'FAIL'}: {check['name']}")
    print(f"Evidence: {args.out}")
    return 0 if report["passed"] and report["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
