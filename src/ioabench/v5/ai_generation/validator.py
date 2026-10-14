from __future__ import annotations

from typing import Any, Mapping

REVIEW_DIMENSIONS = ("construct_fit", "paired_causality", "semantic_consistency", "realism", "structural_novelty")
REQUIRED_REVIEW_FIELDS = REVIEW_DIMENSIONS + ("verdict", "issues")
VERDICTS = {"PASS", "FAIL", "ABSTAIN"}


def validate_review(value: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field in REQUIRED_REVIEW_FIELDS:
        if field not in value:
            findings.append({"code": "REVIEW_FIELD_MISSING", "field_path": f"/{field}", "reason": "required independent review field is missing"})
    scores: list[int] = []
    for field in REVIEW_DIMENSIONS:
        item = value.get(field)
        if not isinstance(item, Mapping):
            findings.append({"code": "REVIEW_DIMENSION_INVALID", "field_path": f"/{field}", "reason": "each dimension must be an object"})
            continue
        score = item.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
            findings.append({"code": "REVIEW_SCORE_INVALID", "field_path": f"/{field}/score", "reason": "score must be an integer from 1 to 5"})
        else:
            scores.append(score)
        if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
            findings.append({"code": "REVIEW_RATIONALE_INVALID", "field_path": f"/{field}/rationale", "reason": "rationale must be non-empty text"})
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(entry, str) or not entry.strip() for entry in evidence):
            findings.append({"code": "REVIEW_EVIDENCE_INVALID", "field_path": f"/{field}/evidence", "reason": "evidence must be a non-empty array of field citations"})
    if value.get("verdict") not in VERDICTS:
        findings.append({"code": "REVIEW_VERDICT_INVALID", "field_path": "/verdict", "reason": "verdict must be PASS, FAIL or ABSTAIN"})
    issues = value.get("issues")
    if not isinstance(issues, list):
        findings.append({"code": "REVIEW_ISSUES_INVALID", "field_path": "/issues", "reason": "issues must be an array"})
    elif any(not isinstance(issue, Mapping) or not all(isinstance(issue.get(key), str) and issue.get(key).strip() for key in ("code", "field_path", "reason", "evidence")) for issue in issues):
        findings.append({"code": "REVIEW_ISSUE_SHAPE_INVALID", "field_path": "/issues", "reason": "each issue needs code, field_path, reason and evidence strings"})
    if len(scores) == len(REVIEW_DIMENSIONS) and isinstance(issues, list):
        expected = "PASS" if min(scores) >= 4 and not issues else "FAIL" if min(scores) <= 2 or issues else "ABSTAIN"
        if value.get("verdict") != expected:
            findings.append({"code": "REVIEW_VERDICT_SCORE_MISMATCH", "field_path": "/verdict", "reason": f"verdict must be {expected} for the supplied scores and issues"})
    return findings


def mock_review(*, structural_novelty: bool = True) -> dict[str, Any]:
    score = 4 if structural_novelty else 2
    issues = [] if structural_novelty else [{"code": "NOVELTY_UNPROVEN", "field_path": "/", "reason": "same structure as prior family", "evidence": "signature"}]
    return {field: {"score": score, "rationale": "deterministic mock review", "evidence": ["/signature"]} for field in REVIEW_DIMENSIONS} | {
        "verdict": "PASS" if structural_novelty else "FAIL", "issues": issues}
