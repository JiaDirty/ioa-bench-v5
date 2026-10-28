from copy import deepcopy
import pytest

from ioabench.v5.ai_generation.quality import validate_semantic_review
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS


def test_resolving_citation_with_false_assertion_is_rejected():
    path = "/candidate/paired_cases/0/world/rounds"
    view = {"paired_cases": [{"world": {"rounds": 4}}, {"world": {"rounds": 4}}],
            "evidence_assertions_required": True}
    review = {name: {"score": 4, "rationale": "The supplied world specifies four rounds.",
                     "evidence": [path], "assertions": [{"path": path, "equals": 4}]}
              for name in REVIEW_DIMENSIONS}
    review.update(verdict="PASS", issues=[])
    assert validate_semantic_review(review, view) == []
    false = deepcopy(review)
    false["semantic_consistency"]["assertions"][0]["equals"] = 5
    assert any(f["code"] == "REVIEW_ASSERTION_UNSUPPORTED"
               for f in validate_semantic_review(false, view))
    missing = deepcopy(review)
    del missing["realism"]["assertions"]
    assert any(f["code"] == "REVIEW_ASSERTION_MISSING"
               for f in validate_semantic_review(missing, view))


def test_boolean_is_not_integer_and_containers_are_not_fact_leaves():
    path = "/candidate/paired_cases/0/world"
    view = {"paired_cases": [{"world": {"rounds": 1}}, {"world": {}}]}
    review = {name: {"score": 4, "rationale": "test", "evidence": [path],
                     "assertions": [{"path": path, "equals": {"rounds": 1}}]}
              for name in REVIEW_DIMENSIONS}
    review.update(verdict="PASS", issues=[])
    assert any(f["code"] == "REVIEW_ASSERTION_UNSUPPORTED"
               for f in validate_semantic_review(review, view))
    leaf = path + "/rounds"
    for dimension in REVIEW_DIMENSIONS:
        review[dimension].update(evidence=[leaf], assertions=[{"path": leaf, "equals": True}])
    assert any(f["code"] == "REVIEW_ASSERTION_UNSUPPORTED"
               for f in validate_semantic_review(review, view))


def test_fact_reference_compiler_preserves_judgment_and_rejects_fabricated_ids():
    from ioabench.v5.ai_generation.quality import assertion_catalog, compile_semantic_review
    view = {"paired_cases": [{"world": {"rounds": 4}}, {"world": {"rounds": 4}}],
            "evidence_assertions_required": True, "review_wire_format": "fact_refs/1"}
    fact = assertion_catalog(view)[0]
    wire = {name: {"score": 2, "rationale": "Deliberately fail this engineering control.",
                   "evidence": ["/candidate/paired_cases/0/world"], "fact_refs": [fact["id"]]}
            for name in REVIEW_DIMENSIONS}
    wire.update(verdict="FAIL", issues=[])
    compiled = compile_semantic_review(wire, view)
    assert compiled["verdict"] == "FAIL" and compiled["construct_fit"]["score"] == 2
    assert compiled["construct_fit"]["assertions"] == [{"path": fact["path"], "equals": 4}]
    assert compiled["construct_fit"]["rationale"] == wire["construct_fit"]["rationale"]
    assert validate_semantic_review(compiled, view) == []
    wire["realism"]["fact_refs"] = ["invented"]
    with pytest.raises(ValueError, match="unknown"):
        compile_semantic_review(wire, view)
