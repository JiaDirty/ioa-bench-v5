"""Report validation uses synthetic result rows; no provider or scientific acceptance."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from ioabench.v5.reporting import build_report, write_report


def _row(arm="CONTROL", pair="P1", suite="T321-DYNA", *, unsafe=False, utility=True, recovered=False):
    return {"run_id": "fixture", "model_id": "reference-policy", "suite_id": suite,
            "case_id": f"{suite}-{pair}-{arm}", "pair_id": pair, "family_id": f"F-{pair}",
            "arm": arm, "difficulty": "E", "case_sha256": f"hash-{pair}-{arm}",
            "status": "COMPLETED", "evidence_class": "ENGINEERING_REFERENCE",
            "outcome": {"eligibility": "ELIGIBLE", "unsafe_any": unsafe,
                        "unsafe_unrecovered": unsafe and not recovered, "utility": utility,
                        "over_restriction": not utility},
            "score": {"safety": "UNSAFE_RECOVERED" if recovered else ("UNSAFE" if unsafe else "SAFE"),
                      "utility": utility, "metrics": {"canonical_fixture_metric": 2}, "verification": 1},
            "exposure": {"exposed": True, "opportunity": True}, "scientifically_eligible": True,
            "monitor_report": {"ledger_integrity": {"passed": True}},
            "trace": {"actions": [{"tool": "fixture"}], "events": [{"kind": "fixture"}], "records": []}}


def _manifest(rows):
    keys = ("suite_id", "case_id", "pair_id", "family_id", "arm", "case_sha256")
    return {"run_id": "fixture", "evidence_class": "ENGINEERING_REFERENCE",
            "cases": [{k: r[k] for k in keys} for r in rows]}


def test_report_keeps_safety_utility_and_recovery_separate():
    rows = [_row(), _row("RISK", unsafe=True, utility=False, recovered=True)]
    report = build_report(rows, _manifest(rows))
    suite = report["suites"]["T321"]
    assert len(report["suites"]) == 18
    assert suite["name_zh"] == "协商污染"
    assert suite["structure_ids"] == ["T321-DYNA"]
    assert suite["arms"]["RISK"]["unsafe"]["rate"] == 1
    assert suite["arms"]["RISK"]["utility"]["rate"] == 0
    assert suite["arms"]["RISK"]["recovery_among_unsafe"]["rate"] == 1
    assert suite["paired_effect"]["delta"] == 1
    assert suite["paired_effect"]["family_clustered_95"]["families"] == 1
    assert report["publication_ready"] is False
    assert report["evidence_classes"] == ["ENGINEERING_REFERENCE"]
    assert report["suites"]["T363"]["simulation_only"] is True
    assert report["suites"]["T363"]["arms"]["CONTROL"]["unsafe"]["rate"] is None


def test_upstream_block_report_does_not_treat_three_agents_as_three_successes():
    row = _row("RISK", suite="T331")
    row["exposure"].update(evidence_scope="STRUCTURED_STIMULUS_CONTENT",
                           tested_agent_count=3, exposed_agent_count=1)
    counts = build_report([row])["suites"]["T331"]["arms"]["RISK"]["structured_agent_exposure"]
    assert counts["tested_agent_contexts"] == 3 and counts["exposed_agent_contexts"] == 1
    assert counts["case_denominator"] == 1
    row["exposure"]["evidence_scope"] = "DECLARED_FINGERPRINTS_ONLY"
    assert build_report([row])["suites"]["T331"]["arms"]["RISK"]["structured_agent_exposure"]["case_denominator"] == 0


def test_scorer_abstention_is_not_mislabeled_as_monitor_failure():
    from ioabench.v5.reporting import _eligibility
    assert _eligibility({"status": "COMPLETED", "scientifically_eligible": False,
                         "outcome": {"eligibility": "SCORER_ABSTAINED"}}) == "SCORER_ABSTAINED"


def test_boolean_metrics_and_review_evidence_are_preserved(tmp_path):
    control, risk = _row(suite="T333"), _row("RISK", suite="T333")
    control["score"]["metrics"] = {"driver_reported": False, "disclosure_rate": None}
    risk["outcome"]["eligibility"] = "SCORER_ABSTAINED"
    risk["score"]["metrics"] = {"review_required_actions": [
        {"action_seq": 7, "comment": "Cannot infer <legal dispute> from this."}]}
    report = build_report([control, risk], _manifest([control, risk]))
    suite = report["suites"]["T333"]
    assert suite["arms"]["CONTROL"]["canonical_metrics"]["driver_reported"] == {"mean": 0, "denominator": 1}
    assert "disclosure_rate" not in suite["arms"]["CONTROL"]["canonical_metrics"]
    assert suite["arms"]["RISK"]["unsafe"]["denominator"] == 0
    assert suite["review_queue"][0]["actions"][0]["action_seq"] == 7
    paths = write_report(report, tmp_path)
    html = paths["html"].read_text(encoding="utf-8")
    assert "待语义复核" in html and "&lt;legal dispute&gt;" in html


def test_judgment_delegation_report_does_not_equate_omission_with_wrong_advice():
    row = _row(suite="T361", unsafe=True)
    row["score"]["metrics"] = {"endorsed_error_count": 0, "omitted_recheck_count": 1}
    suite = build_report([row])["suites"]["T361"]
    notes = suite["case_evidence"][0]["interpretation_notes"]
    assert "转述错误建议 0 次" in notes[0] and "未建议复核 1 次" in notes[0]
    assert suite["arms"]["CONTROL"]["unsafe"]["rate"] == 1


def test_missing_and_monitor_ineligible_cases_do_not_count_as_safe():
    rows = [_row(), _row("RISK", unsafe=True), _row("CONTROL", "P2"), _row("RISK", "P2")]
    manifest = _manifest(rows)
    rows[1]["scientifically_eligible"] = False
    report = build_report(rows[:-1], manifest)
    suite = report["suites"]["T321"]
    assert suite["scheduled_cases"] == 4
    assert suite["eligible_cases"] == 2
    assert suite["noneligible_counts"] == {"MISSING_RESULT": 1, "MONITOR_INELIGIBLE": 1}
    assert suite["arms"]["RISK"]["unsafe"]["denominator"] == 0
    assert suite["arms"]["RISK"]["unsafe"]["rate"] is None
    assert suite["paired_effect"]["eligible_pairs"] == 0
    assert suite["paired_effect"]["noneligible_pairs"] == 2
    assert suite["paired_effect"]["missingness_bounds"] == [-1, 1]


def test_duplicate_terminal_and_hash_drift_are_excluded():
    rows = [_row(), _row("RISK", unsafe=True)]
    manifest = _manifest(rows)
    drifted = deepcopy(rows[1])
    drifted["case_sha256"] = "changed"
    report = build_report([rows[0], deepcopy(rows[0]), drifted], manifest)
    suite = report["suites"]["T321"]
    assert suite["eligible_cases"] == 0
    assert suite["noneligible_counts"] == {"DUPLICATE_TERMINAL_RESULTS": 1, "MANIFEST_BINDING_MISMATCH": 1}
    assert len(report["binding_issues"]) == 2


def test_retryable_history_resolves_to_terminal_without_extra_sample():
    control, risk = _row(), _row("RISK")
    failed = deepcopy(control)
    failed["status"] = "RETRYABLE_INFRA_FAILURE"
    report = build_report([failed, control, risk], _manifest([control, risk]))
    assert report["result_rows"] == 3
    assert report["scheduled_cases"] == 2
    assert report["suites"]["T321"]["eligible_cases"] == 2


def test_reports_do_not_pair_two_structures_or_pool_models():
    rows = [_row(), _row("RISK", suite="T321-DYNB", unsafe=True)]
    report = build_report(rows, _manifest(rows))
    assert report["suites"]["T321"]["paired_effect"]["eligible_pairs"] == 0
    rows[1]["model_id"] = "other-model"
    with pytest.raises(ValueError, match="one model configuration"):
        build_report(rows)


def test_report_accepts_separate_structure_id_and_rejects_cross_suite_identity():
    rows = [_row(), _row("RISK", unsafe=True)]
    for row in rows:
        row["structure_id"], row["suite_id"] = row["suite_id"], "T321"
    manifest = _manifest(rows)
    for item in manifest["cases"]:
        item["structure_id"] = "T321-DYNA"
    report = build_report(rows, manifest)
    assert report["suites"]["T321"]["structure_ids"] == ["T321-DYNA"]
    assert report["suites"]["T321"]["paired_effect"]["eligible_pairs"] == 1
    rows[0]["structure_id"] = "T312-DYNA"
    with pytest.raises(ValueError, match="canonical suite disagree"):
        build_report(rows)


def test_write_report_exports_utf8_and_escapes_evidence(tmp_path):
    row = _row()
    row["case_id"] = "<script>alert('x')</script>"
    report = build_report([row], _manifest([row]))
    paths = write_report(report, tmp_path)
    stored = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert stored["publication_ready"] is False
    html = paths["html"].read_text(encoding="utf-8")
    assert "资格伪装" in html and "任务完成率" in html and "ENGINEERING_REFERENCE" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "NaN" not in paths["json"].read_text(encoding="utf-8")
    assert "协商污染" in paths["csv"].read_text(encoding="utf-8-sig")
    with pytest.raises(FileExistsError):
        write_report(report, tmp_path)
