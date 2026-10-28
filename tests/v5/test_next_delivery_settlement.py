import importlib.util
from pathlib import Path


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/settle_next_delivery.py"
    spec = importlib.util.spec_from_file_location("next_delivery", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_native_cache_derived_totals_keep_original_usage_and_protocol_semantics():
    value = module()
    original = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 20,
                "cache_creation_input_tokens": 30}
    native = value.normalized_usage(original, "anthropic.messages")
    assert native["prompt_tokens"] == 60 and native["total_tokens"] == 65
    assert "prompt_tokens" not in original
    responses = value.normalized_usage({"input_tokens": 60, "output_tokens": 5,
        "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 5}}, "openai.responses")
    assert responses["prompt_tokens"] == 60
    assert responses["prompt_tokens_details"]["cached_tokens"] == 20
    assert responses["cache_creation_input_tokens"] == 5


def test_ledger_never_counts_unknown_usage_or_billing_as_known_zero():
    value = module()
    known = {"terminal": True, "status": "SUCCEEDED", "derived_usage": {"prompt_tokens": 10,
        "completion_tokens": 5, "total_tokens": 16}, "original_usage": {"total_tokens": 16},
        "derived_cost": {"amount": None, "known_subtotal": .25}, "elapsed_seconds": 2}
    unresolved = {"terminal": False, "status": "REQUEST_UNRESOLVED", "derived_usage": {},
        "original_usage": {}, "derived_cost": {"amount": None}, "elapsed_seconds": None}
    result = value.ledger_summary([known, unresolved])
    assert result["unresolved_requests"] == 1 and result["usage_unknown_requests"] == 1
    assert result["billing_unknown_requests"] == 2
    assert result["estimated_usd_known_subtotal"] == .25
    assert result["reported_tokens"]["total_tokens"] == 16
    assert result["reported_arithmetic_token_sum"] == 15
    assert result["reported_usage_inconsistencies"] == 1


def test_only_exact_documented_checkpoint_mutation_is_accepted(tmp_path, monkeypatch):
    import pytest
    value = module()
    monkeypatch.setattr(value, "ROOT", tmp_path)
    directory = tmp_path / "candidate"
    value.evaluation.atomic_json(directory / "checkpoint.json", {"mutable": 1})
    original = value.sha(directory / "checkpoint.json")
    value.evaluation.atomic_json(directory / "RESULT.json", {"evidence_sha256": {"checkpoint.json": original}})
    value.evaluation.atomic_json(directory / "checkpoint.json", {"mutable": 2})
    with pytest.raises(ValueError, match="unexplained"):
        value.candidate_evidence(directory / "RESULT.json", tmp_path)
    value.evaluation.atomic_json(tmp_path / "RESUME_CHECKPOINT_DIAGNOSIS.json", {"changed_files": [{
        "path": "candidate/checkpoint.json", "original_sha256": original,
        "after_resume_sha256": value.sha(directory / "checkpoint.json")} ]})
    assert value.candidate_evidence(directory / "RESULT.json", tmp_path)["evidence_sha256"]["checkpoint.json"] == original
    value.evaluation.atomic_json(directory / "checkpoint.json", {"mutable": 3})
    with pytest.raises(ValueError, match="unexplained"):
        value.candidate_evidence(directory / "RESULT.json", tmp_path)


def test_attempt_ledger_chain_rejects_rewritten_request():
    import pytest
    value = module()
    row = {"event": "REQUEST_STARTED", "previous_event_sha256": "", "requested_model_id": "exact-id"}
    row["event_sha256"] = value.canonical_sha256(row)
    value.verify_event_chain([row])
    row["requested_model_id"] = "substituted"
    with pytest.raises(ValueError, match="hash chain changed"):
        value.verify_event_chain([row])


def test_source_package_keeps_paid_io_and_excludes_large_historical_runners():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/package_next_delivery.py"
    spec = importlib.util.spec_from_file_location("next_package", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    for name in ("model_study/generation/m/task/model_io/attempt-001.json",
                 "development_panel-r1/runner/data/runs/case.jsonl",
                 "fixed_repairs/m/task/PAIR.json"):
        assert value.selected(Path(value.NEXT + name))
    assert value.selected(Path(value.NEXT + "current_history_probes/RUN_CONTRACT.json"))
    assert not value.selected(Path(value.NEXT + "current_history_probes/runner/data/runs/x.json"))
    assert not value.selected(Path(value.NEXT + "current_history_probes/INDEX_WITH_PROBES.json"))
    assert not value.selected(Path(".workbuddy-ai/private.json"))


def test_final_regression_never_inherits_old_pass_or_hides_skipped_tests(tmp_path):
    value = module()
    path = tmp_path / "FINAL_REGRESSION_R3.xml"
    assert value.regression_result(path)["status"] == "NOT_RUN"
    path.write_text('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="0"/></testsuites>', encoding="utf-8")
    assert value.regression_result(path)["status"] == "PASS"
    path.write_text('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="1"/></testsuites>', encoding="utf-8")
    assert value.regression_result(path)["status"] == "FAIL"
