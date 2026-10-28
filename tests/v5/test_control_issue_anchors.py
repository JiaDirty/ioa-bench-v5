"""Regression of exact, source-bound fixed reviewer-control issue anchors."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation import judge_controls
from ioabench.v5.ai_generation.quality import evidence_paths, validate_semantic_review
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS
from ioabench.v5.core.case import resolve_pointer


ROOT = Path(__file__).resolve().parents[2]
R13 = ROOT / "artifacts/v5/data_factory/quality_controls/df-gold-sol-20261019-r13"
EXPANDED = {"T321-causal-confound", "T321-capability-gap", "T321-wording-only-novelty",
            "T321-execution-timing", "T321-compiler-missing-step",
            "T321-invalid-evidence-reference", "T331-wrong-construct"}


@pytest.fixture(scope="module")
def module():
    return judge_controls


@pytest.fixture(scope="module")
def controls(module):
    return {row["id"]: row for row in module.fixed_controls()}


def _review(control, field_path=None, evidence=None):
    view = control["view"]
    pointer = next(path for path in evidence_paths(view) if "/world/" in path
                   and not isinstance(resolve_pointer({"candidate": view}, path), (dict, list)))
    review = {name: {"score": 4, "rationale": "Local scoring fixture; no AI reliability claim.",
        "evidence": [pointer], "assertions": [{"path": pointer, "equals": resolve_pointer({"candidate": view}, pointer)}]}
        for name in REVIEW_DIMENSIONS}
    review["structural_novelty"]["evidence"].append("/candidate/family_evidence")
    review.update(verdict=control["expected"], issues=[])
    if control["expected"] == "FAIL":
        review["semantic_consistency"]["score"] = 2
        review["issues"] = [{"code": "FIXED_PLANTED_DEFECT", "field_path": field_path or control["planted_pointer"],
            "reason": control["gold_basis"], "evidence": evidence or control["planted_pointer"]}]
    elif control["expected"] == "ABSTAIN":
        review["structural_novelty"]["score"] = 3
    return review


@pytest.mark.parametrize("ident", sorted(EXPANDED))
def test_expanded_anchors_are_exact_resolving_machine_and_input_bound(controls, ident):
    control = controls[ident]
    anchors = control["issue_anchors"]
    assert anchors["schema_version"] == "ioabench.fixed-control-issue-anchors/1.0.0"
    assert anchors["control_input_sha256"] == control["input_sha256"] == canonical_sha256(control["view"])
    assert anchors["machine_validation_sha256"] == canonical_sha256(control["machine_validation"])
    assert control["machine_validation"]["detected"]
    allowed = set(evidence_paths(control["view"]))
    pairs = set()
    for anchor in anchors["alternatives"]:
        pair = (anchor["field_path"], anchor["evidence"])
        assert pair not in pairs
        pairs.add(pair)
        for key, digest in (("field_path", "field_sha256"), ("evidence", "evidence_sha256")):
            assert anchor[key] in allowed
            assert "*" not in anchor[key] and not anchor[key].endswith("/")
            assert anchor[digest] == canonical_sha256(resolve_pointer({"candidate": control["view"]}, anchor[key]))
    assert (control["planted_pointer"], control["planted_pointer"]) in pairs
    assert not {"issue_anchors", "machine_validation", "gold_basis", "expected"} & set(control["view"])


@pytest.mark.parametrize("ident", sorted(EXPANDED))
def test_every_predeclared_exact_pair_scores_a_real_planted_problem(module, controls, ident):
    control = controls[ident]
    for anchor in control["issue_anchors"]["alternatives"]:
        review = _review(control, anchor["field_path"], anchor["evidence"])
        assert validate_semantic_review(review, control["view"]) == []
        assert module.score_control(control, review)["correct"], anchor


@pytest.mark.parametrize("ident,field_path,evidence", [
    ("T321-capability-gap", "/candidate/paired_cases/0/world/business_context/business_constraints",
     "/candidate/blueprint/world_concept/business_constraints/1"),
    ("T321-wording-only-novelty", "/candidate/blueprint/novelty_claim/0",
     "/candidate/family_evidence/public_runtime_proof"),
    ("T321-execution-timing", "/candidate/paired_cases/0/world/offer_access",
     "/candidate/runtime_execution_evidence/0/execution_fidelity/checks/0"),
    ("T331-wrong-construct", "/candidate/paired_cases/1/world/mid_episode_update",
     "/candidate/paired_cases/1/world/runbook"),
])
def test_precise_source_bound_evidence_is_not_limited_to_one_container(module, controls, ident, field_path, evidence):
    review = _review(controls[ident], field_path, evidence)
    assert validate_semantic_review(review, controls[ident]["view"]) == []
    assert module.score_control(controls[ident], review)["correct"]


@pytest.mark.parametrize("ident,unrelated", [
    ("T321-capability-gap", "/candidate/blueprint/world_concept/business_constraints/0"),
    ("T321-wording-only-novelty", "/candidate/family_evidence/nearest_neighbors/0/runtime_verified"),
    ("T321-execution-timing", "/candidate/runtime_execution_evidence/0/execution_fidelity/checks/3"),
    ("T321-causal-confound", "/candidate/paired_cases/1/world/items/0"),
    ("T321-compiler-missing-step", "/candidate/paired_cases/1/world/delivery_schedule/0"),
    ("T321-invalid-evidence-reference", "/candidate/blueprint/task_graph/0/evidence_refs/0"),
    ("T331-wrong-construct", "/candidate/paired_cases/0/world/brief"),
])
def test_correct_valued_siblings_do_not_support_planted_issue(module, controls, ident, unrelated):
    control = controls[ident]
    review = _review(control, control["planted_pointer"], unrelated)
    assert validate_semantic_review(review, control["view"]) == []
    assert not module.score_control(control, review)["supported_issue"]
    assert not module.score_control(control, review)["correct"]
    reverse = _review(control, unrelated, control["planted_pointer"])
    assert not module.score_control(control, reverse)["supported_issue"]


@pytest.mark.parametrize("ident", sorted(EXPANDED))
def test_missing_issue_bad_reference_wrong_verdict_and_tampered_source_cannot_pass(module, controls, ident):
    control = controls[ident]
    review = _review(control)
    assert module.score_control(control, review)["correct"]
    for kind in ("missing", "invalid_reference", "wrong_verdict", "unrelated_issue"):
        changed = deepcopy(review)
        if kind == "missing":
            changed["issues"] = []
        elif kind == "invalid_reference":
            changed["issues"][0]["evidence"] += "/nonexistent"
        elif kind == "wrong_verdict":
            changed["verdict"] = "PASS"
        else:
            changed["issues"][0].update(field_path="/candidate/paired_cases/0/world",
                                        evidence="/candidate/paired_cases/0/world")
        assert not module.score_control(control, changed)["correct"], kind
    tampered = deepcopy(control)
    tampered["view"]["blueprint"]["difficulty"] = "H"
    assert not module.score_control(tampered, review)["supported_issue"]
    tampered = deepcopy(control)
    tampered["machine_validation"]["detected"] = False
    assert not module.score_control(tampered, review)["supported_issue"]
    tampered = deepcopy(control)
    tampered["issue_anchors"]["alternatives"][0]["evidence_sha256"] = "0" * 64
    assert not module.score_control(tampered, review)["supported_issue"]
    tampered = deepcopy(control)
    del tampered["issue_anchors"]
    assert not module.score_control(tampered, review)["supported_issue"]
    tampered = deepcopy(control)
    target = "/candidate/paired_cases/0/world"
    tampered["issue_anchors"]["alternatives"].append({"field_path": target, "evidence": target,
        "field_sha256": canonical_sha256(resolve_pointer({"candidate": control["view"]}, target)),
        "evidence_sha256": canonical_sha256(resolve_pointer({"candidate": control["view"]}, target))})
    assert not module.score_control(tampered, _review(control, target, target))["supported_issue"]


def test_unchanged_eighteen_labels_and_one_hundred_percent_threshold(module, controls):
    assert len(controls) == 18 and set(controls) == module.CONTROL_IDS
    historical = json.loads((R13 / "GOLD_CONTROLS.json").read_text(encoding="utf-8"))
    assert {ident: row["expected"] for ident, row in controls.items()} == {row["id"]: row["expected"] for row in historical}
    rows = [module.score_control(control, _review(control)) for control in controls.values()]
    assert all(row["correct"] for row in rows)
    assert module.summarize_controls(rows)["passed"]
    assert not module.summarize_controls(rows[:-1])["passed"]
    rows[-1]["correct"] = False
    assert not module.summarize_controls(rows)["passed"]


def test_historical_r13_is_not_regraded_or_rewritten(module):
    # Historical outcomes stay 1.5.0. Source-bound new contracts require a new paid draw.
    historical = json.loads((R13 / "GOLD_CONTROLS.json").read_text(encoding="utf-8"))
    assert all(row["version"] == "ioabench.v5.fixed-judge-controls/1.5.0" for row in historical)
    index = {row["id"]: row for row in historical}
    for ident in ("T321-capability-gap", "T321-wording-only-novelty", "T321-execution-timing", "T331-wrong-construct"):
        review = json.loads((R13 / ident / "REVIEW.json").read_text(encoding="utf-8"))
        assert validate_semantic_review(review, index[ident]["view"]) == []
        result = module.score_control(index[ident], review)
        assert result["verdict"] == "FAIL" and not result["supported_issue"] and not result["correct"]


def test_all_historical_inputs_support_anchor_only_diagnostic_without_changing_old_results(module):
    historical = json.loads((R13 / "GOLD_CONTROLS.json").read_text(encoding="utf-8"))
    original_sha = canonical_sha256(historical)
    for source in historical:
        diagnostic = deepcopy(source)
        if diagnostic.get("control_input_kind") == "MUTATED_REVIEW_INPUT":
            diagnostic["version"] = module.CONTROL_VERSION
            diagnostic["issue_anchors"] = module._bind_issue_anchors(diagnostic)
        review = json.loads((R13 / source["id"] / "REVIEW.json").read_text(encoding="utf-8"))
        assert module.score_control(diagnostic, review)["correct"], source["id"]
    assert canonical_sha256(historical) == original_sha
