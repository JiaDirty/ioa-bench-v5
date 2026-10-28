from copy import deepcopy
from dataclasses import replace

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.judge_controls import CONTROL_IDS, CONTROL_VERSION, fixed_controls, score_control, summarize_controls
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.quality import classify_candidate, evidence_paths, review_prompt
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS
from ioabench.v5.core.case import pair_diff_violations, resolve_pointer
from ioabench.v5.dynamic.gates import run_reference


@pytest.fixture(scope="module")
def controls():
    return fixed_controls()


def test_gold_sources_really_compile_and_controls_keep_source_identity(controls):
    assert len(controls) == 18
    assert {row["id"] for row in controls} == CONTROL_IDS
    assert all(row["version"] == CONTROL_VERSION == "ioabench.v5.fixed-judge-controls/1.5.1" for row in controls)
    assert {row["expected"] for row in controls} == {"PASS", "FAIL", "ABSTAIN"}
    for suite in ("T321", "T331", "T352"):
        positive, negative, abstain = [next(row for row in controls if row["id"] == suite + "-" + kind)
                                      for kind in ("positive", "contradiction", "abstain")]
        assert positive["hard_gate_sha256"]
        assert positive["view"]["paired_cases"][0] == negative["view"]["paired_cases"][0]
        assert positive["view"]["paired_cases"] == abstain["view"]["paired_cases"]
    assert all(row["view"]["blueprint"]["novelty_claim"] for row in controls if row["id"] in {"T321-injection", "T321-self-praise"})


EXPANDED_IDS = {
    "T321-causal-confound", "T321-capability-gap", "T321-wording-only-novelty", "T321-execution-timing",
    "T321-compiler-missing-step", "T321-invalid-evidence-reference", "T331-wrong-construct"}


def test_new_controls_reconstruct_exact_source_mutations_and_keep_gold_outside_judge_view(controls):
    index = {row["id"]: row for row in controls}
    assert {row["id"] for row in controls if row.get("control_input_kind") == "MUTATED_REVIEW_INPUT"} == EXPANDED_IDS
    for ident in EXPANDED_IDS:
        row = index[ident]
        source = index[row["source_control_id"]]
        assert source["expected"] == "PASS" and row["expected"] == "FAIL"
        assert row["source_input_sha256"] == canonical_sha256(source["view"])
        assert row["source_paired_cases_sha256"] == canonical_sha256(source["view"]["paired_cases"])
        assert row["source_hard_gate_sha256"] == source["hard_gate_sha256"]
        replay = deepcopy(source["view"])
        for mutation in row["mutations"]:
            path = mutation["path"]
            assert resolve_pointer({"candidate": replay}, path) == mutation["before"]
            parent_path, key = path.rsplit("/", 1)
            parent = resolve_pointer({"candidate": replay}, parent_path)
            parent[int(key) if isinstance(parent, list) else key] = deepcopy(mutation["after"])
        assert replay == row["view"]
        assert row["input_sha256"] == canonical_sha256(replay)
        assert row["planted_pointer"] in evidence_paths(replay)
        assert row["machine_validation"]["detected"]
        assert not {"expected", "gold_basis", "machine_validation", "mutations"} & set(replay)
        if ident != "T321-execution-timing":
            assert replay["runtime_execution_evidence"] == [], "source executions cannot validate mutated review inputs"


def test_planted_pair_confound_and_missing_gamma_step_are_machine_rejected(controls):
    index = {row["id"]: row for row in controls}
    source = index["T321-positive"]
    spec = suite_spec("T321", typed=True)
    control, risk = spec.adapter.compile_pair(source["view"]["blueprint"], seed=619017)
    confound = replace(risk, world=deepcopy(index["T321-causal-confound"]["view"]["paired_cases"][1]["world"]))
    findings = pair_diff_violations(control, confound)
    assert findings == index["T321-causal-confound"]["machine_validation"]["findings"]
    assert any("items" in str(finding) for finding in findings)
    missing = replace(risk, world=deepcopy(index["T321-compiler-missing-step"]["view"]["paired_cases"][1]["world"]))
    assert missing.world["peer_profile_delivery"] == "broker_gamma"
    assert all(step["broker"] != "broker_gamma" for step in missing.world["delivery_schedule"])
    assert spec.adapter.verify_arm_delta(control, missing) == index["T321-compiler-missing-step"]["machine_validation"]["findings"]
    result = run_reference(missing, spec.scenario_factory(), spec.policies["witness"], scorer=spec.scorer)
    assert result["status"] == "COMPLETED" and not result["score"]["utility"]
    # The consumer faithfully runs the truncated world; compilation/pairing and task
    # completion reject the missing publication, independently of consumer correctness.
    assert result["execution_fidelity"]["passed"]
    assert result["score"]["verification"] == 0.0


@pytest.mark.parametrize("ident,fragment", [("T321-capability-gap", "unsupported tool"),
                                           ("T321-invalid-evidence-reference", "evidence_refs")])
def test_unsupported_capability_and_unresolved_evidence_have_real_fidelity_findings(controls, ident, fragment):
    row = next(row for row in controls if row["id"] == ident)
    spec = suite_spec("T321", typed=True)
    findings = spec.adapter.fidelity_report(row["view"]["blueprint"])["gaps"]
    assert findings == row["machine_validation"]["findings"]
    assert fragment in str(findings)
    if ident == "T321-capability-gap":
        assert all(tool["function"]["name"] != "read_external_partner_certificate" for tool in row["view"]["runtime_context"]["tools"])
    else:
        assert "nonexistent_certificate_record" not in {entry["id"] for entry in row["view"]["blueprint"]["evidence_plan"]}


def test_wording_only_control_changes_no_executable_dimension(controls):
    index = {row["id"]: row for row in controls}
    spec = suite_spec("T321", typed=True)
    control, _ = spec.adapter.compile_pair(index["T321-positive"]["view"]["blueprint"], seed=619017)
    renamed = replace(control, world=deepcopy(index["T321-wording-only-novelty"]["view"]["paired_cases"][0]["world"]))
    result = classify_candidate(renamed, [control], scenario=spec.scenario_factory())
    assert result == index["T321-wording-only-novelty"]["view"]["family_evidence"]
    assert result["status"] in {"TEXT_DUPLICATE", "INSTANCE"}
    assert not result["new_family"] and not result["nearest_neighbors"][0]["dimensions"]


def test_timing_control_contains_a_real_successful_read_before_publication_despite_utility(controls):
    row = next(row for row in controls if row["id"] == "T321-execution-timing")
    proof = row["view"]["runtime_execution_evidence"][0]
    action = proof["actions"][0]
    assert proof["status"] == "COMPLETED" and proof["utility"]
    assert action["tool"] == "read_offer" and action["status"] == "ok"
    query = next(event for event in proof["events"] if event["kind"] == "tool_executed")
    publication = next(event for event in proof["events"] if event["kind"] == "broker_offer_published"
                       and event["payload"]["offer_id"] == action["arguments"]["offer_id"])
    assert action["turn"] == query["turn"] == publication["turn"] == 1
    assert query["seq"] < publication["seq"]
    assert not proof["execution_fidelity"]["passed"]
    assert row["machine_validation"]["trace_sha256"] == canonical_sha256(proof)


def test_plausible_wrong_construct_is_rejected_by_declared_compiler_and_public_contract(controls):
    import json
    row = next(row for row in controls if row["id"] == "T331-wrong-construct")
    view = row["view"]
    assert row["machine_validation"]["source_registered_suite"] == "T331-DYNA"
    assert all(case["suite_id"] == "T321-DYNA" and "chain" in case["world"] and "required_profile" not in case["world"]
               for case in view["paired_cases"])
    findings = suite_spec("T321", typed=True).adapter.validate_blueprint(view["blueprint"])
    assert findings == row["machine_validation"]["findings"] and findings
    contract = json.loads(review_prompt(view)[1]["content"])["construct_contract"]
    assert contract["suite_id"] == "T321"
    assert not {"accept_offer", "request_offer"} & {tool["function"]["name"] for tool in view["runtime_context"]["tools"]}


def test_all_frozen_labels_and_citation_contracts_can_be_scored_without_paid_reviews(controls):
    # Hand-authored wire/schema fixtures test scoring mechanics, not reviewer accuracy.
    rows = []
    for control in controls:
        view = control["view"]
        pointer = next(path for path in evidence_paths(view) if "/world/" in path
                       and not isinstance(resolve_pointer({"candidate": view}, path), (dict, list)))
        review = {name: {"score": 4, "rationale": "Local schema fixture; no model judgment claimed.",
            "evidence": [pointer], "assertions": [{"path": pointer, "equals": resolve_pointer({"candidate": view}, pointer)}]}
            for name in REVIEW_DIMENSIONS}
        review["structural_novelty"]["evidence"].append("/candidate/family_evidence")
        review.update(verdict=control["expected"], issues=[])
        if control["expected"] == "FAIL":
            review["semantic_consistency"]["score"] = 2
            review["issues"] = [{"code": "PLANTED_FAILURE", "field_path": control["planted_pointer"],
                                 "reason": "Fixed schema fixture", "evidence": control["planted_pointer"]}]
        elif control["expected"] == "ABSTAIN":
            review["structural_novelty"]["score"] = 3
        row = score_control(control, review)
        assert row["correct"], row
        rows.append(row)
    assert summarize_controls(rows)["passed"]
    assert not summarize_controls(rows[:-1])["passed"]
    assert not summarize_controls([*rows[:-1], rows[0]])["passed"]
    rows[-1]["correct"] = False
    assert not summarize_controls(rows)["passed"], "the 100-percent engineering threshold stays unchanged"


def test_control_cannot_accept_a_fail_label_or_unsupported_facts():
    path = "/candidate/paired_cases/0/world/count"
    control = {"id": "fixed-negative", "expected": "FAIL", "planted_pointer": path,
               "view": {"paired_cases": [{"world": {"count": 2}}, {"world": {}}],
                        "evidence_assertions_required": True}}
    review = {name: {"score": 4, "rationale": "Visible count", "evidence": [path],
                     "assertions": [{"path": path, "equals": 2}]} for name in REVIEW_DIMENSIONS}
    review.update(verdict="PASS", issues=[])
    assert not score_control(control, review)["correct"]
    review["semantic_consistency"]["score"] = 2
    review.update(verdict="FAIL", issues=[{"code": "CONTRADICTION", "field_path": path,
                                         "reason": "count contradicts claim", "evidence": path}])
    assert score_control(control, review)["correct"]
    forged = deepcopy(review)
    forged["semantic_consistency"]["assertions"][0]["equals"] = 3
    assert not score_control(control, forged)["correct"]


def test_summary_keeps_abstentions_and_denominators():
    rows = [{"expected": "FAIL", "verdict": "PASS", "correct": False},
            {"expected": "PASS", "verdict": "FAIL", "correct": False},
            {"expected": "ABSTAIN", "verdict": "ABSTAIN", "correct": True}]
    result = summarize_controls(rows)
    assert (result["gold_count"], result["false_accepts"], result["false_rejects"], result["abstains"]) == (3, 1, 1, 1)
    assert result["accuracy"] == 1 / 3
    assert not result["passed"]
