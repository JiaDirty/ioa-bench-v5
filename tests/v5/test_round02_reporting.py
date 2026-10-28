"""Unexecuted tasks and missing usage cannot become zero-cost successes."""
import importlib.util
from pathlib import Path
import sys


def module():
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("round02_report", scripts / "report_round02_comparison.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_cost_keeps_unknown_attempt_in_denominator():
    report = module()
    value = report.cost([{"cost": {"amount": .25}}, {"status": "REQUEST_UNRESOLVED"}])
    assert value["known_subtotal_usd"] == .25 and value["total_estimated_usd"] is None
    assert value["actual_bill_usd"] is None and value["missing_usage_or_rate_attempts"] == 1
    assert report.cost([])["total_estimated_usd"] is None


def test_missing_reasoning_and_explicit_policy_refusal_are_distinct():
    report = module()
    assert report.reasoning_tokens({}) is None
    assert report.reasoning_tokens({"output_tokens_details": {"thinking_tokens": 9}}) == 9
    assert report.reasoning_tokens({"completion_tokens_details": {"reasoning_tokens": 0}}) == 0
    assert report.response_category({"status": "FAILED", "category": "RESPONSE_PARSE",
                                    "response": {"finish_reason": "refusal"}}) == "PROVIDER_POLICY_REFUSAL"


def test_request_table_keeps_http401_and_missing_tokens(tmp_path):
    report = module()
    row, = report.request_rows(tmp_path, [{"evidence": "quality/m--high/q1/model_io/task/attempt-001.json",
        "evidence_sha256": "sha", "requested_model_id": "m", "request_id": "task", "request_sha256": "request",
        "status": "FAILED", "category": "AUTH/PERMISSION", "error": 'HTTP 401; {"http_status": "401"}'}], [])
    assert row["http_code"] == 401 and row["input_tokens"] == row["reasoning_tokens"] == "UNKNOWN"
    assert row["schema_pass"] == row["quality_pass"] == "NOT_RUN"


def test_unexecuted_config_has_no_rank_no_cost_no_qualification(tmp_path):
    report = module()
    config = {"id": "model--high", "model": "model", "protocol": "openai.responses",
              "parameters": {"reasoning": {"effort": "high"}}}
    row, = report.scorecard(tmp_path, {"configs": [config]}, [])
    assert row["R_NOT_RUN"] == row["Q_NOT_RUN"] == 8
    assert row["weighted_engineering_score"] is row["engineering_cost_per_pair_usd"] is None
    assert row["usage_reported"] is None and row["auditor_qualified"] is False
    assert row["R_Wilson95"] is None
    assert row["engineering_pair_Wilson95"] is None
