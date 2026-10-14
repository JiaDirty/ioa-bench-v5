from __future__ import annotations

from scripts.v5.verify_system import _adapter_map, _check_reference_behavior
from ioabench.v5.core.case import SUITES
from ioabench.v5.dynamic import registry
from ioabench.v5.suites import load


def test_reference_behavior_gate_checks_every_suite_arm_and_exposure():
    adapters = _adapter_map()
    cases = [case for adapter in adapters.values() for pair in adapter.generate(seed=11, families=1)[:1]
             for case in pair]
    rows = []
    for case in cases:
        safety = adapters[case.suite_id].EXPECTED_REFERENCE["naive"][case.arm]
        rows.append({"case_id": case.case_id, "status": "COMPLETED", "scientifically_eligible": True,
                     "simulation_only": case.simulation_only,
                     "exposure": {"exposed": True, "opportunity": True},
                     "score": {"safety": safety},
                     "outcome": {"unsafe_any": safety in {"UNSAFE", "UNSAFE_RECOVERED"}}})

    assert _check_reference_behavior(cases, rows, "naive", adapters)["passed"]
    risk_case = next(case for case in cases if case.arm == "RISK")
    wrong_score = next(row for row in rows if row["case_id"] == risk_case.case_id)
    wrong_score["score"]["safety"] = "SAFE"
    result = _check_reference_behavior(cases, rows, "naive", adapters)
    assert not result["passed"]
    assert any(issue.get("reason") == "reference safety mismatch" and issue["case_id"] == risk_case.case_id
               for issue in result["issues"])


def test_reference_behavior_gate_rejects_missing_exposure_and_duplicate_rows():
    adapters = _adapter_map()
    cases = [case for case in (load("T311").generate(seed=11, families=1)[0]
                              + registry.get_adapter("T311-DYNA").generate(seed=11, families=1)[0])]
    rows = []
    for case in cases:
        safety = adapters[case.suite_id].EXPECTED_REFERENCE["witness"][case.arm]
        rows.append({"case_id": case.case_id, "status": "COMPLETED", "scientifically_eligible": True,
                     "simulation_only": case.simulation_only, "exposure": {"exposed": False, "opportunity": True},
                     "score": {"safety": safety}, "outcome": {"unsafe_any": False}})

    result = _check_reference_behavior(cases, rows + [rows[0]], "witness", adapters)
    assert not result["passed"]
    assert any(issue.get("reason") == "stimulus or decision opportunity not observed" for issue in result["issues"])
    assert any(issue.get("reason") == "unexpected or duplicate result" for issue in result["issues"])
