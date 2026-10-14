"""Per-pair offline validity gates for v5 cases (ADR-V5-000 P1, P2, P3, P5).

``check_pair`` runs, without any provider, every check a generated CONTROL/RISK pair must pass
before it can enter a dataset:

1. pair diff limited to declared mechanism slots;
2. static observation-firewall scan of both worlds;
3. decision witness reaches SAFE + utility in both arms with exposure and opportunity proven;
4. scorer sensitivity: naive/recovery reference policies receive their expected safety labels.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ioabench.models import ModelProfile
from ioabench.v5.core.case import Case, pair_diff_violations
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.firewall import LeakageViolation, ObservationFirewall
from ioabench.v5.suites import load

GATES_VERSION = "v5-pair-gates-1.1.0"
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


async def run_reference(case: Case, policy_name: str) -> dict[str, Any]:
    module = load(case.suite_id)
    scenario = getattr(module, f"{case.suite_id}Scenario")()
    model = module.policies()[policy_name]
    auxiliary = module.reference_auxiliary() if hasattr(module, "reference_auxiliary") else None
    try:
        trace = await run_episode(case, scenario, model, PROFILE, parameters={"temperature": 0.0}, auxiliary=auxiliary)
    except LeakageViolation as exc:
        return {"policy": policy_name, "arm": case.arm, "status": "LEAKAGE", "detail": str(exc)}
    proof = case_exposure_proof(trace.records, case, trace.decision_tools)
    result: dict[str, Any] = {"policy": policy_name, "arm": case.arm, "status": trace.status, "exposure": proof,
                              "model_calls": len(trace.records), "detail": trace.error_detail}
    if trace.status == "COMPLETED":
        result["score"] = module.score(trace, case).as_dict()
    return result


def check_pair(control: Case, risk: Case) -> dict[str, Any]:
    module = load(control.suite_id)
    scenario = getattr(module, f"{control.suite_id}Scenario")()
    failures: list[str] = []
    diff = pair_diff_violations(control, risk)
    if diff:
        failures.append(f"pair diff outside mechanism slots: {diff}")
    for case in (control, risk):
        findings = ObservationFirewall(extra_terms=scenario.firewall_terms(case.world)).scan(dict(case.world))
        if findings:
            failures.append(f"{case.arm} world firewall findings: {[(f.path, f.match) for f in findings[:5]]}")
    runs = []
    for policy_name, expected in module.EXPECTED_REFERENCE.items():
        for case in (control, risk):
            run = asyncio.run(run_reference(case, policy_name))
            runs.append(run)
            label = f"{policy_name}/{case.arm}"
            if run["status"] != "COMPLETED":
                failures.append(f"{label}: status {run['status']} {run.get('detail') or ''}")
                continue
            if not (run["exposure"]["exposed"] and run["exposure"]["opportunity"]):
                failures.append(f"{label}: exposure/opportunity not proven")
            safety = run["score"]["safety"]
            if safety != expected[case.arm]:
                failures.append(f"{label}: safety {safety} != expected {expected[case.arm]}")
            if policy_name == "witness" and not run["score"]["utility"]:
                failures.append(f"{label}: witness did not achieve utility")
    return {"gates_version": GATES_VERSION, "suite_id": control.suite_id, "pair_id": control.pair_id,
            "passed": not failures, "failures": failures, "runs": runs}
