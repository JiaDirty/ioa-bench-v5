"""Pair gates for dynamic-world slices (adapter-parameterized variant of v5 gates).

Mirrors `ioabench.v5.gates.check_pair` but takes the slice's scenario/scorer/policies
explicitly instead of resolving them through the frozen 18-suite registry, and adds the
slice's fine-grained arm-delta whitelist. Same pass conditions, same evidence quality.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Mapping

from ioabench.models import ModelProfile
from ioabench.v5.core.case import Case, pair_diff_violations
from ioabench.v5.core.engine import BaseScenario, run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.firewall import LeakageViolation, ObservationFirewall

DYNAMIC_GATES_VERSION = "v5-dynamic-pair-gates-0.3.0"
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def run_reference(case: Case, scenario: BaseScenario, model: Any, *,
                  scorer: Callable[[Any, Case], Any]) -> dict[str, Any]:
    auxiliary = getattr(scenario, "reference_auxiliary", lambda: None)()
    try:
        trace = asyncio.run(run_episode(case, scenario, model, PROFILE,
                                        parameters={"temperature": 0.0}, auxiliary=auxiliary))
    except LeakageViolation as exc:
        return {"policy": getattr(model, "name", "?"), "arm": case.arm, "status": "LEAKAGE", "detail": str(exc)}
    proof = case_exposure_proof(trace.records, case, trace.decision_tools)
    result: dict[str, Any] = {"policy": getattr(model, "name", "?"), "arm": case.arm, "status": trace.status,
                              "exposure": proof, "model_calls": len(trace.records), "detail": trace.error_detail}
    if trace.status == "COMPLETED":
        result["score"] = scorer(trace, case).as_dict()
        fidelity = getattr(scenario, "execution_fidelity", None)
        if fidelity is not None:
            result["execution_fidelity"] = fidelity(trace, case.world)
    return result


def check_pair_dynamic(control: Case, risk: Case, *, scenario: BaseScenario,
                       scorer: Callable[[Any, Case], Any], policies: Mapping[str, Any],
                       expected: Mapping[str, Mapping[str, str]],
                       fine_arm_delta: Callable[[Case, Case], list[str]] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    diff = pair_diff_violations(control, risk)
    if diff:
        failures.append(f"pair diff outside mechanism slots: {diff}")
    if fine_arm_delta is not None:
        fine = fine_arm_delta(control, risk)
        if fine:
            failures.append(f"fine arm-delta whitelist violations: {fine}")
    for case in (control, risk):
        findings = ObservationFirewall(extra_terms=scenario.firewall_terms(case.world)).scan(dict(case.world))
        if findings:
            failures.append(f"{case.arm} world firewall findings: {[(f.path, f.match) for f in findings[:5]]}")
    runs = []
    for policy_name, model in policies.items():
        for case in (control, risk):
            run = run_reference(case, scenario, model, scorer=scorer)
            runs.append(run)
            label = f"{policy_name}/{case.arm}"
            if run["status"] != "COMPLETED":
                failures.append(f"{label}: status {run['status']} {run.get('detail') or ''}")
                continue
            if not (run["exposure"]["exposed"] and run["exposure"]["opportunity"]):
                failures.append(f"{label}: exposure/opportunity not proven")
            safety = run["score"]["safety"]
            if safety != expected[policy_name][case.arm]:
                failures.append(f"{label}: safety {safety} != expected {expected[policy_name][case.arm]}")
            if policy_name == "witness" and not run["score"]["utility"]:
                failures.append(f"{label}: witness did not achieve utility")
            if not run.get("execution_fidelity", {"passed": True})["passed"]:
                failures.append(f"{label}: executable field-consumer proof failed: {run['execution_fidelity']['findings']}")
    return {"gates_version": DYNAMIC_GATES_VERSION, "pair_id": control.pair_id,
            "passed": not failures, "failures": failures, "runs": runs}
