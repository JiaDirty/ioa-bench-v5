import csv
import importlib.util
import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256


SPEC = importlib.util.spec_from_file_location("development_report", Path(__file__).resolve().parents[2] / "scripts/v5/report_development_factory.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def submissions(out, entries):
    previous, rows = "", []
    for entry in entries:
        row = {"at_utc": "2026-10-20T10:01:00+00:00", "provider": "deepseek", "previous_event_sha256": previous, **entry}
        if row["event"] == "REQUEST_FINISHED":
            row.setdefault("status", "PASS")
        row["event_sha256"] = canonical_sha256(row)
        previous = row["event_sha256"]
        rows.append(row)
    path = out / "REQUEST_LEDGER.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def accepted_pair(out, identifier="new-accepted"):
    source = out / "candidates" / identifier
    result = {"status": "PASS", "task": {"id": identifier, "suite": "T331"}, "reference_and_replay_count": 6}
    write(source / "RESULT.json", result)
    write(source / "HARD_GATE.json", {"passed": True})
    audit = {"status": "DEV_AUTO_AUDITED", "reviews": [
        {"effort": effort, "review": {"verdict": "ACCEPT"}, "validation_errors": []} for effort in ("high", "max")]}
    destination = out / "reviews" / identifier
    write(destination / "audit/AUDIT_RESULT.json", audit)
    admission = {"id": identifier, "suite": "T331", "status": "DEV_ACCEPTED", "source_directory": str(source),
        "audit_status": "DEV_AUTO_AUDITED", "hard_gate_errors": [], "recorded_strict_replays": 6,
        "history_scope": "FULL_HISTORY", "structural_vector": {"runtime_consumed": {"topology": "chain"}, "structural_cell_sha256": "cell-one"},
        "formal_accepted": False, "same_model_audit_independent_science": False,
        "source_result_sha256": report.sha(source / "RESULT.json"), "audit_result_sha256": canonical_sha256(audit)}
    write(destination / "ADMISSION.json", admission)
    return source, destination, admission


def test_report_keeps_failure_unknown_and_not_run_denominators(tmp_path):
    out = tmp_path
    accepted_pair(out)
    write(out / "candidates/hard-failed/RESULT.json", {"status": "FAIL", "task": {"id": "hard-failed", "suite": "T362"}, "failed_stage": "HISTORY_NONDUPLICATE"})
    write(out / "candidates/hard-failed/HARD_GATE.json", {"passed": True})
    write(out / "plans/PLAN.json", {"tasks": [{"id": name, "suite": "T331"} for name in ("new-accepted", "hard-failed", "pending", "never-run")]})
    submissions(out, [
        {"event": "REQUEST_INTENT", "directory": "candidates/new-accepted/model_io", "request_id": "generate"},
        {"event": "REQUEST_FINISHED", "directory": "candidates/new-accepted/model_io", "request_id": "generate", "cost": {"lower_cny": 1, "upper_cny": 2}, "usage": {"prompt_tokens": 12}, "transport": {"http_status": 200, "elapsed_seconds": 3}},
        {"event": "REQUEST_INTENT", "directory": "reviews/new-accepted/audit/model_io", "request_id": "audit-high", "parameters": {"reasoning_effort": "high"}},
        {"event": "REQUEST_FINISHED", "directory": "reviews/new-accepted/audit/model_io", "request_id": "audit-high", "cost": {"lower_cny": 2, "upper_cny": 4}},
        {"event": "REQUEST_INTENT", "directory": "candidates/pending/model_io", "request_id": "pending"},
        {"event": "REQUEST_FAILED", "request_id": "pending", "category": "REQUEST_UNRESOLVED"},
    ])
    summary = report.build(out)
    assert summary["generation_terminal_fail"] == 1
    assert summary["planned_generation_unique_ids"] == 4
    assert summary["generation_planned_not_run"] == ["never-run"]
    assert summary["unknown_terminal_requests"] == 1
    assert summary["new_spend"]["lower_cny"] == 3 and summary["new_spend"]["upper_cny"] is None
    assert summary["unit_new_batch_spend_per_dev_accepted"]["upper_cny"] is None
    assert summary["audit_calibration"]["status"] == "NOT_RUN"
    assert summary["stability"]["long_term_stability_established"] is False
    assert len((out / "DEV_POOL_INDEX.jsonl").read_text("utf-8").splitlines()) == 1
    with (out / "PAIR_QUALITY.csv").open(encoding="utf-8") as stream:
        quality = {row["id"]: row for row in csv.DictReader(stream)}
    assert quality["hard-failed"]["status"] == "REJECTED" and quality["hard-failed"]["audit_status"] == "NOT_RUN"
    assert quality["pending"]["status"] == "QUARANTINED_INCOMPLETE"
    with (out / "MECHANISM_COVERAGE.csv").open(encoding="utf-8") as stream:
        assert len(list(csv.DictReader(stream))) == 18
    before = report.sha(out / "DEV_POOL_INDEX.jsonl")
    report.build(out)
    assert report.sha(out / "DEV_POOL_INDEX.jsonl") == before


def test_false_acceptance_and_ledger_mutation_fail_closed(tmp_path):
    source, destination, admission = accepted_pair(tmp_path)
    admission["history_scope"] = "VERSION_SCOPED"
    write(destination / "ADMISSION.json", admission)
    with pytest.raises(ValueError, match="DEV_ACCEPTED contradicts"):
        report.build(tmp_path)
    submissions(tmp_path, [{"event": "REQUEST_INTENT", "directory": "candidates/x", "request_id": "id"}])
    path = tmp_path / "REQUEST_LEDGER.jsonl"
    path.write_text(path.read_text("utf-8").replace("candidates/x", "candidates/y"), encoding="utf-8")
    with pytest.raises(ValueError, match="ledger chain"):
        report.ledger(path)


def test_zero_acceptance_has_no_fabricated_unit_cost_or_calibration_pass(tmp_path):
    write(tmp_path / "AUDIT_CALIBRATION.json", {"planned": 6, "executed": 2, "model_rejection_passes": 2, "hard_gate_rejection_passes": 2})
    value = report.build(tmp_path)
    assert value["unit_new_batch_spend_per_dev_accepted"]["status"] == "NO_ACCEPTED_PAIRS"
    assert value["unit_new_batch_spend_per_dev_accepted"]["lower_cny"] is None
    assert value["audit_calibration"]["status"] == "FAIL"
    assert not value["formal_scientific_claims"]


def test_reused_generation_cost_is_sunk_and_text_does_not_add_structural_cells(tmp_path):
    out = tmp_path
    accepted_pair(out)
    previous = out / "retained"
    source = previous / "candidates/old-replayfix"
    source.mkdir(parents=True)
    write(source / "RESULT.json", {"status": "PASS", "task": {"id": "old-replayfix", "suite": "T331"}})
    write(previous / "candidates/old-original/RESULT.json", {"status": "FAIL", "task": {"suite": "T331"}})
    write(previous / "MODEL_CATALOG.json", [{"id": "deepseek-flash"}])
    write(source / "GENERATION_REUSE.json", {"source_candidate": str(previous / "candidates/old-intermediate")})
    write(previous / "candidates/old-intermediate/GENERATION_REUSE.json", {"source_candidate": str(previous / "candidates/old-original")})
    write(out / "BASELINE_CENSUS.json", {"pairs": [{"id": "old-replayfix", "suite": "T331", "source_directory": str(source),
        "reference_replay_rows": 6, "vector": {"structural_cell_sha256": "cell-one", "runtime_consumed": {"topology": "chain"}}}], "pair_count": 1})
    write(out / "reviews/old-replayfix/audit/AUDIT_RESULT.json", {"status": "REJECTED", "reviews": [
        {"effort": "high", "review": {"verdict": "REJECT"}, "validation_errors": []},
        {"effort": "max", "validation_errors": ["REVIEW_RESPONSE_OR_PROVIDER_INVALID"]}]})
    submissions(previous, [
        {"event": "REQUEST_INTENT", "directory": "candidates/old-original/model_io", "request_id": "old"},
        {"event": "REQUEST_FINISHED", "directory": "candidates/old-original/model_io", "request_id": "old", "cost": {"lower_cny": 1, "upper_cny": 2}}])
    value = report.build(out)
    assert value["new_spend"]["request_intents"] == 0
    assert value["reused_audited_baseline_sunk_generation"] == {"lower_cny": 1, "upper_cny": 2}
    index = json.loads((out / "EVIDENCE_INDEX.json").read_text("utf-8"))
    binding = index["external_generation_cost_and_reuse_bindings"]["old-replayfix"]
    assert binding["files"]["retained/REQUEST_LEDGER.jsonl"] == report.sha(previous / "REQUEST_LEDGER.jsonl")
    assert binding["files"]["retained/MODEL_CATALOG.json"] == report.sha(previous / "MODEL_CATALOG.json")
    assert binding["chain_directories"] == ["retained/candidates/old-replayfix", "retained/candidates/old-intermediate", "retained/candidates/old-original"]
    assert value["audit_disagreements"] == 0
    assert value["audit_protocol_failure_responses"] == 1
    with (out / "MECHANISM_COVERAGE.csv").open(encoding="utf-8") as stream:
        row = next(row for row in csv.DictReader(stream) if row["suite"] == "T331")
    assert row["baseline_cells"] == "1" and row["new_verified_executable_cells"] == "0"


def test_retained_32_and_generated_audits_keep_distinct_denominators(tmp_path):
    baseline = []
    for ordinal in range(32):
        identifier = f"retained-{ordinal}"
        if ordinal == 0:
            source, _, admission = accepted_pair(tmp_path, identifier)
            vector = admission["structural_vector"]
        else:
            source = tmp_path / "candidates" / identifier
            write(source / "RESULT.json", {"status": "PASS", "task": {"suite": "T331"}})
            vector = {"runtime_consumed": {"topology": "chain"}, "structural_cell_sha256": "cell-one"}
        baseline.append({"id": identifier, "suite": "T331", "source_directory": str(source), "vector": vector})
    write(tmp_path / "BASELINE_CENSUS.json", {"pairs": baseline, "pair_count": 32})
    write(tmp_path / "reviews/retained-1/audit/AUDIT_RESULT.json", {"status": "REJECTED", "reviews": [
        {"effort": effort, "review": {"verdict": "REJECT"}, "validation_errors": []} for effort in ("high", "max")]})
    write(tmp_path / "plans/AUDIT_ALL_RETAINED_V11.json", {"ids": [row["id"] for row in baseline]})
    write(tmp_path / "plans/SUPPLEMENTAL.json", {"ids": ["supplemental-audit"]})
    accepted_pair(tmp_path, "generated-with-accompanying-audit")
    summary = report.build(tmp_path)
    assert summary["baseline_pairs"] == 32 and summary["planned_audit_unique_ids"] == 33
    assert summary["audit_completed_pairs"] == 3 and summary["retained_baseline_audit_completed_pairs"] == 2
    assert summary["dev_accepted_pairs"] == 2
    assert summary["retained_baseline_dev_accepted_pairs"] == summary["new_candidate_dev_accepted_pairs"] == 1
    assert len(summary["audit_planned_not_run"]) == 31 and "supplemental-audit" in summary["audit_planned_not_run"]
    snapshot = next(row for row in summary["plan_snapshots"] if row["file"].endswith("AUDIT_ALL_RETAINED_V11.json"))
    assert len(snapshot["audit_ids"]) == 32
    text = (tmp_path / "ROUND_REPORT.md").read_text("utf-8")
    assert "原基线审核完成2/32对" in text and "新生成入池1对，旧基线复用入池1对" in text
    assert "显式审核计划33个唯一ID（另有生成阶段附随审核）；全部来源完成3对" in text
    actions = (tmp_path / "NEXT_ACTIONS.md").read_text("utf-8")
    assert "DeepSeek官方控制台轮换" in actions and "DEEPSEEK_API_KEY/.env" in actions
    assert "不回显、不写入证据" in actions and "不阻塞已授权研发执行" in actions


def test_truncated_response_usage_is_counted_without_promoting_it_to_valid_completion(tmp_path):
    submissions(tmp_path, [
        {"event": "REQUEST_INTENT", "directory": "reviews/x/audit/model_io", "request_id": "max"},
        {"event": "REQUEST_FAILED", "request_id": "max", "category": "RESPONSE_PARSE",
         "cost": {"lower_cny": 2, "upper_cny": 4}, "usage": {"completion_tokens": 16384}}])
    value = report.build(tmp_path)
    assert value["complete_responses"] == 0 and value["unknown_terminal_requests"] == 0
    assert value["new_spend"]["upper_cny"] == 4
    assert value["new_spend"]["usage"]["completion_tokens"] == 16384


def test_reconciled_failure_receipts_are_billed_once_and_never_count_as_success(tmp_path):
    receipt = tmp_path / "attempt.json"
    write(receipt, {"raw_usage": 32768})
    submissions(tmp_path, [
        {"event": "REQUEST_INTENT", "directory": "reviews/x/audit/model_io", "request_id": "max"},
        {"event": "REQUEST_FAILED", "request_id": "max", "category": "RESPONSE_PARSE"},
        {"event": "REQUEST_FINISHED", "directory": "reviews/x/audit/model_io", "request_id": "max", "status": "FAILED_WITH_RESPONSE",
         "cost": {"lower_cny": 2, "upper_cny": 4}, "usage": {"completion_tokens": 32768},
         "transport": {"http_status": 200}, "receipt_path": "attempt.json", "receipt_sha256": report.sha(receipt)},
        {"event": "REQUEST_FAILED", "directory": "reviews/x/audit/model_io", "request_id": "max", "category": "RESPONSE_PARSE"},
    ])
    value = report.build(tmp_path)
    assert value["new_spend"]["upper_cny"] == 4 and value["request_intents"] == 1
    assert value["complete_responses"] == 0 and value["http200_responses"] == 1
    assert value["unknown_terminal_requests"] == 0
    receipt.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="accounting receipt changed"):
        report.ledger(tmp_path / "REQUEST_LEDGER.jsonl")


def test_forensic_preserves_baseline_and_quarantines_only_affected_trace(tmp_path):
    pairs = []
    for identifier, suite in (("old-T352-01", "T352"), ("old-T331-01", "T331")):
        source = tmp_path / "retained/candidates" / identifier
        write(source / "RESULT.json", {"status": "PASS", "task": {"suite": suite}})
        write(source / "HARD_GATE.json", {"passed": True})
        pairs.append({"id": identifier, "suite": suite, "source_directory": str(source),
            "reference_replay_rows": 6, "vector": {"structural_cell_sha256": suite, "runtime_consumed": {"topology": "chain"}}})
    write(tmp_path / "BASELINE_CENSUS.json", {"pairs": pairs, "pair_count": 2})
    baseline_before = report.sha(tmp_path / "BASELINE_CENSUS.json")
    rows = []
    for ordinal in range(8):
        rows.append({"pair_id": "old-T352-01" if ordinal < 6 else "old-T331-01",
            "historical_observations": {"compared": 30, "not_observed_in_a_later_request": int(ordinal == 7),
                "mismatches": [{"tool": "read_history"}] * 27 if ordinal < 6 else [], "alignment_errors": []},
            "current_engine_reanalysis": {"checks": {"requests": True, "score": True}}})
    write(tmp_path / "FORENSIC_TRACE_ALIASING.json", {"baseline_sha256": baseline_before,
        "engine_version": "v5-episode-engine-1.4.4", "affected_pair_ids": ["old-T352-01"], "rows": rows})
    value = report.build(tmp_path)
    assert value["baseline_pairs"] == 2 and value["quarantined_pairs"] == 1
    facts = value["trace_aliasing_forensic"]
    assert facts["mismatched_reference_rows"] == 6 and facts["result_mismatches"] == 162
    assert facts["pairs_without_observed_contradiction"] == 1
    assert facts["current_engine_reanalysis_pass"] == 8 and not facts["strict_historical_replay_replaced"]
    assert facts["terminal_results_unobserved"] == 1
    quarantine = json.loads((tmp_path / "QUARANTINE_INDEX.jsonl").read_text("utf-8"))
    assert quarantine["id"] == "old-T352-01" and quarantine["status"] == "QUARANTINED_TRACE_PAYLOAD_INCONSISTENCY"
    assert quarantine["recorded_admission_status"] == "DEV_ENGINEERING_VALID"
    assert report.sha(tmp_path / "BASELINE_CENSUS.json") == baseline_before
    text = (tmp_path / "ROUND_REPORT.md").read_text("utf-8")
    assert "reanalysis" in text and "UNKNOWN" in text and "162" in text
    write(tmp_path / "BASELINE_CENSUS.json", {"pairs": []})
    with pytest.raises(ValueError, match="different baseline"):
        report.build(tmp_path)


def test_calibration_separates_decision_rejection_invalid_refs_and_valid_disagreement(tmp_path):
    verdicts = [("REJECT", "REJECT"), ("REJECT", "ACCEPT"), ("REJECT", "ACCEPT")]
    for ordinal, pair in enumerate(verdicts, 1):
        write(tmp_path / f"calibration/case-{ordinal}/AUDIT_RESULT.json", {"status": "QUARANTINED", "reviews": [
            {"review": {"verdict": verdict}, "validation_errors": ["EVIDENCE_REF_INVALID"]
             if ordinal in {1, 3} and index == 1 else []} for index, verdict in enumerate(pair)]})
    write(tmp_path / "AUDIT_CALIBRATION.json", {"planned": 3, "executed": 3,
        "model_rejection_passes": 3, "rows": [{"model_rejection_pass": True, "hard_gate_enforced": True}] * 3})
    value = report.build(tmp_path)["audit_calibration"]
    assert value["status"] == "FAIL" and value["reported_model_rejection_passes"] == 3
    assert value["decision_rejection_passes"] == 1 and value["model_rejection_passes"] == 0
    assert value["invalid_evidence_reference_responses"] == 2
    assert value["verdict_disagreements"] == 2 and value["contract_valid_verdict_disagreements"] == 1
    assert value["decision_rejections_with_invalid_contract"] == 1
    assert value["hard_gate_rejection_passes"] == 3


def test_calibration_requires_per_case_flag_and_raw_valid_contract_for_pass(tmp_path):
    write(tmp_path / "calibration/case-1/AUDIT_RESULT.json", {"status": "REJECTED", "reviews": [
        {"review": {"verdict": "REJECT"}, "validation_errors": []} for _ in range(2)]})
    calibration = {"planned": 1, "executed": 1, "model_rejection_passes": 1,
        "rows": [{"model_rejection_pass": False, "hard_gate_enforced": True}]}
    write(tmp_path / "AUDIT_CALIBRATION.json", calibration)
    assert report.build(tmp_path)["audit_calibration"]["status"] == "FAIL"
    calibration["rows"][0]["model_rejection_pass"] = True
    write(tmp_path / "AUDIT_CALIBRATION.json", calibration)
    assert report.build(tmp_path)["audit_calibration"]["status"] == "PASS"
    write(tmp_path / "calibration/case-1/AUDIT_RESULT.json", {"status": "REJECTED", "reviews": [
        {"review": {"verdict": "REJECT"}} for _ in range(2)]})
    assert report.build(tmp_path)["audit_calibration"]["status"] == "FAIL"


def test_unknown_terminal_and_budget_reserve_are_not_fabricated_completion_costs(tmp_path):
    submissions(tmp_path, [
        {"event": "REQUEST_INTENT", "directory": "reviews/x/audit/model_io", "request_id": "unknown"},
        {"event": "REQUEST_FAILED", "request_id": "unknown", "category": "UNKNOWN"},
        {"event": "REQUEST_INTENT", "directory": "reviews/x/audit/model_io", "request_id": "missing-usage"},
        {"event": "REQUEST_FINISHED", "directory": "reviews/x/audit/model_io", "request_id": "missing-usage",
         "cost": {"status": "UNKNOWN", "currency": "CNY"}, "usage": {}, "budget_reserve_cny": 9.5},
        {"event": "REQUEST_INTENT", "directory": "reviews/x/audit/model_io", "request_id": "invalid-json"},
        {"event": "REQUEST_FINISHED", "directory": "reviews/x/audit/model_io", "request_id": "invalid-json",
         "status": "FAILED_WITH_RESPONSE", "cost": {"lower_cny": 1, "upper_cny": 2}, "usage": {"completion_tokens": 16}},
        {"event": "REQUEST_FAILED", "directory": "reviews/x/audit/model_io", "request_id": "invalid-json", "category": "RESPONSE_PARSE"},
    ])
    value = report.build(tmp_path)
    assert value["unknown_terminal_requests"] == 1
    assert value["new_spend"]["lower_cny"] == 1 and value["new_spend"]["upper_cny"] is None
    assert value["new_spend"]["recorded_budget_reserve_cny"] == 9.5
    assert not value["new_spend"]["budget_reserve_is_billed_cost"]


def test_structure_capacity_is_reported_without_promoting_preflight_to_generated_pool(tmp_path):
    write(tmp_path / "STRUCTURE_CAPACITY.json", {"suites": [{"suite": "T322", "compiled_cell_upper_bound": 2,
        "finite_axes": {"native_record_access": ["direct", "receipt_reference"]},
        "capacity_basis": "Compiler enumeration of two runtime-consumed paths", "limits": ["No arbitrary topology"],
        "reference_verified_planned_cells": 2}]})
    write(tmp_path / "COVERAGE_ALLOCATION.json", {"suites": [{"suite": "T322", "compiled_cell_upper_bound": 2,
        "requested_goal": 3, "goal_unreachable_in_current_finite_grammar": True, "planned_fresh_cells": 2,
        "status": "CAPACITY_SATURATED_BELOW_GOAL", "history_scope": "VERSION_SCOPED_HISTORY_INDETERMINATE"}]})
    write(tmp_path / "T362_STRUCTURE_PREFLIGHT.json", {"status": "PASS",
        "scope": "OFFLINE_DEVELOPMENT_STRUCTURE_PREFLIGHT_NOT_MODEL_GENERATED_POOL", "provider_calls": 0,
        "cases_entered_pool": 0, "pairs": 12, "reference_runs": 72,
        "strict_recorded_response_replays": 72, "distinct_structure_cells": 6})
    # Root plans become executable denominators only after the runner snapshots them into plans/.
    write(tmp_path / "PLAN_COVERAGE_V1.json", {"tasks": [{"id": "not-executed", "suite": "T322"}]})
    summary = report.build(tmp_path)
    assert summary["generation_terminal_pass"] == summary["request_intents"] == summary["dev_accepted_pairs"] == 0
    assert summary["planned_generation_unique_ids"] == 0
    preflight = summary["t362_structure_preflight"]
    assert preflight["pairs"] == 12 and preflight["strict_recorded_response_replays"] == 72
    assert preflight["accepted_pairs_inferred"] == preflight["model_generated_pairs_inferred"] == 0
    coverage = {row["suite"]: row for row in summary["mechanism_coverage"]}
    assert coverage["T322"]["compiled_cell_upper_bound"] == 2
    assert coverage["T322"]["structure_goal_status"] == "CURRENT_FINITE_GRAMMAR_BOUND_BELOW_GOAL"
    assert coverage["T322"]["capacity_limits"] == ["No arbitrary topology"]
    assert coverage["T331"]["capacity_status"] == "NOT_RUN"
    assert coverage["T362"]["program_preflight_structure_cells"] == 6
    assert coverage["T362"]["known_executable_cells"] == coverage["T362"]["accepted_cells"] == 0
    text = (tmp_path / "SUITE18_READINESS.md").read_text("utf-8")
    assert "当前有限语法上限不足3" in text and "native_record_access" in text
    assert "程序构造12对" in text and "cases_entered_pool=0" in text


def test_capacity_conflicts_fail_closed_and_missing_preflight_is_not_run(tmp_path):
    summary = report.build(tmp_path)
    assert summary["structure_capacity_evidence"]["status"] == "NOT_RUN"
    assert summary["t362_structure_preflight"]["status"] == "NOT_RUN"
    write(tmp_path / "STRUCTURE_CAPACITY.json", {"suites": [{"suite": "T322", "compiled_cell_upper_bound": 2}]})
    write(tmp_path / "COVERAGE_ALLOCATION.json", {"suites": [{"suite": "T322", "compiled_cell_upper_bound": 3}]})
    with pytest.raises(ValueError, match="capacity and allocation disagree"):
        report.build(tmp_path)


def test_unadmitted_t322_keeps_recorded_history_scope(tmp_path):
    write(tmp_path / "plans/PLAN.json", {"tasks": [{"id": "t322-scoped", "suite": "T322",
        "history_scope": "VERSION_SCOPED"}]})
    report.build(tmp_path)
    with (tmp_path / "PAIR_QUALITY.csv").open(encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["history_scope"] == "VERSION_SCOPED" and row["status"] == "NOT_RUN"
    assert not (tmp_path / "DEV_POOL_INDEX.jsonl").read_text("utf-8")


def test_audit_effort_pairs_require_same_input_protocol_and_all_other_parameters(tmp_path):
    entries = []
    for identifier, protocol, budgets in (("paired", "audit/1.1", (65536, 65536)),
                                          ("different-budget", "audit/1.1", (32768, 65536)),
                                          ("missing-binding", "audit/1.1", (65536, 65536))):
        reviews = []
        write(tmp_path / f"reviews/{identifier}/audit/AUDIT_PACKET.json", {"version": protocol})
        for effort, budget in zip(("high", "max"), budgets):
            request_id = identifier + "-" + effort
            directory = f"reviews/{identifier}/audit/model_io"
            review = {"effort": effort, "request_id": request_id, "review": {"verdict": "ACCEPT"},
                      "validation_errors": ["EVIDENCE_REF_INVALID"] if identifier == "paired" and effort == "high" else []}
            reviews.append(review)
            entries.append({"event": "REQUEST_INTENT", "directory": directory, "request_id": request_id,
                "messages_sha256": identifier if identifier != "missing-binding" else None,
                "tools_sha256": "tools", "parameters": {"reasoning_effort": effort, "max_tokens": budget,
                                                           "response_format": {"type": "json_object"}}})
            entries.append({"event": "REQUEST_FINISHED", "directory": directory, "request_id": request_id,
                "cost": {"lower_cny": 1, "upper_cny": 2}, "usage": {"completion_tokens": 10}})
        write(tmp_path / f"reviews/{identifier}/audit/AUDIT_RESULT.json", {"status": "QUARANTINED", "reviews": reviews})
    submissions(tmp_path, entries)
    summary = report.build(tmp_path)
    comparison = summary["audit_same_input_effort_comparison"]
    assert comparison["paired_inputs"] == 1 and comparison["requests_without_comparison_binding"] == 2
    assert comparison["unpaired_or_repeated_condition_groups"] == 2
    assert comparison["by_effort"]["high"]["contract_valid"] == 0
    assert comparison["by_effort"]["high"]["cost_per_contract_valid_review"]["status"] == "NO_CONTRACT_VALID_REVIEWS"
    assert comparison["by_effort"]["max"]["cost_per_contract_valid_review"]["upper_cny"] == 2
    assert not comparison["pairs"][0]["both_contract_valid"]
    assert sum(row["request_intents"] for row in summary["audit_parameter_conditions"]) == 6
    assert sum(row["invalid_evidence_reference_responses"] for row in summary["audit_parameter_conditions"]) == 1


def test_complete_audit_with_invalid_json_keeps_completion_and_separate_error_categories(tmp_path):
    write(tmp_path / "candidates/t362-json/RESULT.json", {"status": "PASS", "task": {"suite": "T362"}})
    write(tmp_path / "reviews/t362-json/audit/AUDIT_RESULT.json", {"status": "QUARANTINED", "reviews": [
        {"effort": "high", "request_id": "high", "review": {"verdict": "REJECT", "error_codes": ["CAUSAL_MISSING"]},
         "validation_errors": []},
        {"effort": "max", "request_id": "max", "provider_category": "RESPONSE_PARSE",
         "validation_errors": ["REVIEW_RESPONSE_OR_PROVIDER_INVALID"]}]})
    entries = []
    for effort in ("high", "max"):
        entries += [{"event": "REQUEST_INTENT", "directory": "reviews/t362-json/audit/model_io", "request_id": effort,
                     "parameters": {"reasoning_effort": effort}},
                    {"event": "REQUEST_FINISHED", "directory": "reviews/t362-json/audit/model_io", "request_id": effort,
                     "cost": {"lower_cny": 1, "upper_cny": 2}, "transport": {"http_status": 200}}]
    submissions(tmp_path, entries)
    summary = report.build(tmp_path)
    assert summary["complete_responses"] == summary["http200_responses"] == 2
    assert summary["unknown_terminal_requests"] == summary["failure_event_count"] == 0
    assert summary["failure_categories"] == {}
    assert summary["audit_response_error_categories"] == {"RESPONSE_PARSE": 1}
    assert summary["audit_validation_error_counts"] == {"REVIEW_RESPONSE_OR_PROVIDER_INVALID": 1}
    assert summary["audit_semantic_error_code_counts"] == {"CAUSAL_MISSING": 1}
    assert summary["audit_semantic_reject_responses"] == 1 and summary["audit_protocol_failure_responses"] == 1
    with (tmp_path / "PAIR_QUALITY.csv").open(encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert json.loads(row["audit_response_error_categories"]) == {"RESPONSE_PARSE": 1}
    assert json.loads(row["audit_validation_error_counts"]) == {"REVIEW_RESPONSE_OR_PROVIDER_INVALID": 1}
    assert json.loads(row["audit_semantic_error_code_counts"]) == {"CAUSAL_MISSING": 1}


def test_explicit_original_root_relocates_baseline_and_reuse_cost_without_host_fallback(tmp_path, monkeypatch, capsys):
    original, extracted = tmp_path / "original", tmp_path / "extracted"
    original.mkdir()
    extracted.mkdir()
    monkeypatch.setattr(report, "ROOT", extracted)
    out = extracted / "current"
    replay, intermediate, paid = [extracted / "prior/candidates" / name for name in ("replay", "intermediate", "paid")]
    write(replay / "RESULT.json", {"status": "PASS", "task": {"suite": "T331"}})
    write(replay / "GENERATION_REUSE.json", {"source_candidate": str(original / "prior/candidates/intermediate")})
    write(intermediate / "GENERATION_REUSE.json", {"source_candidate": "prior/candidates/paid"})
    write(paid / "RESULT.json", {"status": "FAIL"})
    write(extracted / "prior/MODEL_CATALOG.json", [{"id": "deepseek-flash"}])
    submissions(extracted / "prior", [
        {"event": "REQUEST_INTENT", "directory": "candidates/paid/model_io", "request_id": "paid"},
        {"event": "REQUEST_FINISHED", "directory": "candidates/paid/model_io", "request_id": "paid",
         "cost": {"lower_cny": 1, "upper_cny": 2}}])
    write(original / "prior/candidates/replay/RESULT.json", {"status": "FAIL", "wrong_checkout": True})
    write(out / "BASELINE_CENSUS.json", {"pairs": [{"id": "replay", "suite": "T331",
        "source_directory": str(original / "prior/candidates/replay"), "vector": {}}]})
    write(out / "reviews/replay/audit/AUDIT_RESULT.json", {"status": "QUARANTINED", "reviews": []})
    with pytest.raises(ValueError, match="escapes"):
        report.build(out)
    original_hash = report.sha(original / "prior/candidates/replay/RESULT.json")
    summary = report.build(out, original_root=original)
    assert summary["reused_audited_baseline_sunk_generation"] == {"lower_cny": 1, "upper_cny": 2}
    assert summary["path_mapping"]["fallback_to_original_workspace"] is False
    monkeypatch.setattr(report.sys, "argv", ["report_development_factory.py", "--out", str(out), "--original-root", str(original)])
    report.main()
    assert json.loads(capsys.readouterr().out)["baseline_pairs"] == 1
    index = json.loads((out / "EVIDENCE_INDEX.json").read_text("utf-8"))
    binding = index["external_generation_cost_and_reuse_bindings"]["replay"]
    assert Path(binding["root"]) == extracted
    assert binding["chain_directories"] == ["prior/candidates/replay", "prior/candidates/intermediate", "prior/candidates/paid"]
    assert binding["files"]["prior/REQUEST_LEDGER.jsonl"] == report.sha(extracted / "prior/REQUEST_LEDGER.jsonl")
    assert report.sha(original / "prior/candidates/replay/RESULT.json") == original_hash
    with (out / "PAIR_QUALITY.csv").open(encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["engineering_status"] == "PASS" and Path(row["source_directory"]) == replay
    assert report.source_path("prior/candidates/paid", out, original) == paid
    # A missing relocated file must remain missing, even when the original exists.
    (replay / "RESULT.json").unlink()
    assert report.source_path(original / "prior/candidates/replay/RESULT.json", out, original) == replay / "RESULT.json"
    assert not report.source_path(original / "prior/candidates/replay/RESULT.json", out, original).exists()


def test_original_root_mapping_rejects_other_absolute_prefix_relative_escape_and_reuse_escape(tmp_path, monkeypatch):
    extracted, original = tmp_path / "extracted", tmp_path / "original"
    extracted.mkdir()
    monkeypatch.setattr(report, "ROOT", extracted)
    out = extracted / "current"
    with pytest.raises(ValueError, match="absolute prefix"):
        report.build(out, original_root=Path("relative-original"))
    with pytest.raises(ValueError, match="original-root prefix"):
        report.source_path(tmp_path / "other/candidate", out, original)
    with pytest.raises(ValueError, match="escapes"):
        report.source_path("../../outside", out, original)
    source = extracted / "prior/candidates/reuse"
    write(source / "GENERATION_REUSE.json", {"source_candidate": str(tmp_path / "other/candidates/paid")})
    with pytest.raises(ValueError, match="original-root prefix"):
        report.generation_binding(source, extracted, out, original)


def t321_limitation_fixture(out):
    identifier = "coverage-T321-01"
    source = out / "candidates" / identifier
    review = out / "reviews" / identifier
    write(source / "RESULT.json", {"status": "PASS", "task": {"suite": "T321"}})
    audit = {"status": "QUARANTINED", "reviews": [
        {"effort": effort, "review": {"verdict": verdict}, "validation_errors": []}
        for effort, verdict in (("high", "REJECT"), ("max", "ACCEPT"))]}
    write(review / "audit/AUDIT_RESULT.json", audit)
    write(review / "ADMISSION.json", {"status": "QUARANTINED", "suite": "T321", "source_directory": str(source)})
    paths = [source / "RESULT.json", review / "ADMISSION.json", review / "audit/AUDIT_RESULT.json"]
    evidence = {"version": "ioabench.v5.t321-design-fidelity-limitation/1.0.0",
        "verification_status": "PASS_READ_ONLY_FACT_BINDING", "candidate_id": identifier,
        "source_bindings": [{"path": str(path), "sha256": report.sha(path), "bytes": path.stat().st_size} for path in paths],
        "findings": [{"id": "GAMMA_AND_LATE_RELEASE_NOT_EXECUTED"}, {"id": "CLEAN_CLOSE_DECLARATION_NOT_ENFORCED"},
                     {"id": "BROKER_COUNTER_IS_NOT_BUSINESS_DELIVERY"}],
        "original_reviews": audit["reviews"], "retained_admission_status": "QUARANTINED",
        "disposition": {"candidate_status": "QUARANTINED", "original_review_results_unchanged": True},
        "original_evidence_modified": False, "original_audit_rewritten": False, "independent_scientific_review": False}
    write(out / "T321_DESIGN_FIDELITY_LIMITATION.json", evidence)
    return paths, evidence


def test_t321_limitations_are_bound_and_reported_without_changing_admission_counts(tmp_path):
    accepted_pair(tmp_path)
    assert report.build(tmp_path)["t321_design_fidelity_limitation"]["status"] == "NOT_RUN"
    paths, evidence = t321_limitation_fixture(tmp_path)
    before = {path: report.sha(path) for path in paths}
    value = report.build(tmp_path)
    facts = value["t321_design_fidelity_limitation"]
    assert facts["status"] == "PASS_READ_ONLY_FACT_BINDING" and facts["source_bindings_verified"] == len(paths)
    assert facts["original_reviews"] == evidence["original_reviews"]
    assert facts["retained_admission_status"] == "QUARANTINED" and not facts["original_audit_rewritten"]
    assert value["dev_accepted_pairs"] == value["quarantined_pairs"] == value["audit_disagreements"] == 1
    assert value["audit_completed_pairs"] == 2 and value["request_intents"] == 0
    quarantine = json.loads((tmp_path / "QUARANTINE_INDEX.jsonl").read_text("utf-8"))
    assert quarantine["id"] == "coverage-T321-01" and quarantine["status"] == "QUARANTINED"
    for filename in ("ROUND_REPORT.md", "NEXT_ACTIONS.md"):
        text = (tmp_path / filename).read_text("utf-8")
        assert "T321_DESIGN_FIDELITY_LIMITATION.json" in text and "coverage-T321-01" in text
        assert "两broker/initial" in text and "clean-close合规测评" in text and "deliveries_done" in text
        assert "high REJECT、max ACCEPT、分歧和QUARANTINED全部保留" in text
    assert {path: report.sha(path) for path in paths} == before
    index = json.loads((tmp_path / "EVIDENCE_INDEX.json").read_text("utf-8"))
    assert index["files"][facts["file"]] == facts["sha256"]


@pytest.mark.parametrize("change", ["content", "bytes", "sha256", "missing"])
def test_t321_limitation_rejects_any_changed_or_missing_binding_before_reporting(tmp_path, change):
    paths, evidence = t321_limitation_fixture(tmp_path)
    if change == "missing":
        paths[-1].unlink()
    elif change == "content":
        write(paths[-1], {"tampered": True})
    else:
        evidence["source_bindings"][-1][change] = -1 if change == "bytes" else "0" * 64
        write(tmp_path / "T321_DESIGN_FIDELITY_LIMITATION.json", evidence)
    with pytest.raises(ValueError, match="T321 design limitation source binding changed"):
        report.build(tmp_path)
    assert not (tmp_path / "ROUND_REPORT.md").exists()
    assert not (tmp_path / "COST_AND_YIELD.json").exists()


def test_t321_limitation_maps_original_paths_only_to_extracted_sources(tmp_path, monkeypatch):
    original, extracted = tmp_path / "original", tmp_path / "extracted"
    monkeypatch.setattr(report, "ROOT", extracted)
    out = extracted / "round"
    paths, evidence = t321_limitation_fixture(out)
    for binding, path in zip(evidence["source_bindings"], paths):
        binding["path"] = str(original / path.relative_to(extracted))
    write(out / "T321_DESIGN_FIDELITY_LIMITATION.json", evidence)
    facts = report.t321_design_fidelity(out, original_root=original)
    assert facts["source_bindings_verified"] == len(paths)
    paths[-1].unlink()
    write(original / "round/reviews/coverage-T321-01/audit/AUDIT_RESULT.json", {"original_is_not_a_fallback": True})
    with pytest.raises(ValueError, match="source binding changed"):
        report.t321_design_fidelity(out, original_root=original)
