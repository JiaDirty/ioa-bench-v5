"""Gold diagnosis must expose evidence limits without changing original judgments."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SPEC = spec_from_file_location("diagnose_r13_gold", Path(__file__).resolve().parents[2] / "scripts/v5/diagnose_r13_gold.py")
diagnosis = module_from_spec(SPEC)
SPEC.loader.exec_module(diagnosis)


def control(expected="FAIL", ident="T321-capability-gap"):
    return {"id": ident, "expected": expected}


def score(verdict="FAIL", *, supported=True, correct=True, findings=None):
    return {"verdict": verdict, "supported_issue": supported, "correct": correct, "findings": findings or []}


def test_typed_assertion_and_pointer_checks_do_not_claim_semantic_support():
    values = {}
    facts = diagnosis.cited_facts({"world": {"flag": True}}, {
        "construct_fit": {"evidence": ["/candidate/world/flag", "/candidate/missing"],
                          "assertions": [{"path": "/candidate/world/flag", "equals": 1}]},
        "issues": [{"field_path": None, "evidence": "/candidate/world/flag"}]}, values)
    assert facts[0]["citation_true"] and facts[0]["actual_value"] is True
    assert facts[1]["citation_true"] is False
    assert facts[2]["assertion_true"] is False  # True and numeric 1 are distinct JSON values.
    assert facts[3]["citation_true"] is False
    assert values[facts[0]["actual_value_sha256"]] is True
    assert all("semantic_support" not in item for item in facts)


def test_true_reference_with_wrong_anchor_remains_failed_unadjudicated():
    facts = [{"review_location": "/issues/0/evidence", "citation_true": True}]
    outcome = score(supported=False, correct=False)
    assert diagnosis.classify(control(), outcome, facts) == ["VALID_EVIDENCE_BUT_NARROW_ANCHOR"]
    assert outcome["correct"] is False


def test_injection_only_is_not_evidence_of_the_planted_count_contradiction():
    facts = [{"review_location": "/issues/0/evidence", "citation_true": True}]
    assert diagnosis.classify(control(ident="T321-injection"), score(supported=False, correct=False), facts) == [
        "EVIDENCE_DOES_NOT_ESTABLISH_PLANTED_DEFECT"]


def test_false_accept_and_broken_citation_are_both_reported():
    categories = diagnosis.classify(control(), score("PASS", supported=False, correct=False,
        findings=[{"code": "REVIEW_CITATION_UNRESOLVED"}]), [])
    assert categories == ["TRUE_MODEL_FALSE_ACCEPT", "JSON_OR_PROTOCOL_ERROR"]


def test_positive_abstain_is_not_silently_reclassified_as_model_failure_or_pass():
    assert diagnosis.classify(control("PASS", "T352-positive"), score("ABSTAIN", correct=False), []) == ["GOLD_AMBIGUITY"]
    assert diagnosis.classify(control("ABSTAIN"), score("ABSTAIN"), []) == ["ABSTAIN_FOR_VALID_UNCERTAINTY"]
    assert diagnosis.classify(control("FAIL"), score("ABSTAIN", correct=False,
        findings=[{"code": "REVIEW_VERDICT_SCORE_MISMATCH"}]), []) == ["JSON_OR_PROTOCOL_ERROR"]


def test_truncated_response_is_not_a_judgment_even_if_partial_verdict_exists():
    assert diagnosis.classify(control(), score("PASS", correct=False), [], finish_reason="length") == ["TRUNCATION"]
    assert diagnosis.classify(control(), None, []) == ["NOT_RUN"]


def test_immutable_output_accepts_exact_resume_and_rejects_changed_bytes(tmp_path):
    path = tmp_path / "result.json"
    diagnosis.write_once(path, {"passed": False})
    before = path.read_bytes()
    diagnosis.write_once(path, {"passed": False})
    with pytest.raises(ValueError, match="immutable output differs"):
        diagnosis.write_once(path, {"passed": True})
    assert path.read_bytes() == before


def test_nested_binding_records_preserve_all_original_sha_checks():
    record = {"path": "old/review.json", "sha256": "a" * 64}
    assert list(diagnosis.bound_records({"draws": [{"review": record}]})) == [record]
