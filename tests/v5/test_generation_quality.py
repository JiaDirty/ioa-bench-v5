from __future__ import annotations

from copy import deepcopy
import json

import pytest
from jsonschema import Draft202012Validator

from ioabench.v5.ai_generation.quality import (QUALITY_VERSION, build_review_view,
    classify_candidate, dedup_features, evidence_paths, public_runtime_context, review_prompt,
    semantic_review_schema, validate_semantic_review)
from ioabench.v5.ai_generation.t352_compiler import T352DynaCompiler
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS
from ioabench.v5.dynamic import t321_slice, t331_slice, t352_slice
from ioabench.v5.suites import t321 as classic_t321


def _pair():
    return next(iter(t321_slice.generate(seed=9, families=1)))


def _view():
    control, risk = _pair()
    return build_review_view({"suite_id": "T321", "claim": "An untrusted proposal."}, control, risk)


def _review():
    return {dimension: {"score": 4, "rationale": "The compiled policy supports this finding.",
                        "evidence": ["/candidate/paired_cases/0/world/policy"]}
            for dimension in REVIEW_DIMENSIONS} | {"verdict": "PASS", "issues": []}


def test_public_pair_omits_oracle_and_generator_identity_without_mutation():
    control, risk = _pair()
    before = deepcopy(control.as_dict())
    view = build_review_view({"suite_id": "T321"}, control, risk)
    assert all("oracle" not in case and "provenance" not in case for case in view["paired_cases"])
    assert control.as_dict() == before
    view["paired_cases"][0]["world"]["policy"] = "changed only in review copy"
    assert control.as_dict() == before


@pytest.mark.parametrize("suite", ["T311", "T312", "T313", "T321", "T322", "T323",
                                  "T331", "T332", "T333", "T341", "T342", "T343",
                                  "T351", "T352", "T353", "T361", "T362", "T363"])
def test_reviewer_receives_authoritative_construct_definition_without_case_answers(suite):
    from hashlib import sha256
    from pathlib import Path
    from ioabench.v5.dynamic.registry import get_adapter
    control, risk = get_adapter(suite + "-DYNA").generate(seed=9, families=1)[0]
    view = build_review_view({}, control, risk)
    before = deepcopy(view)
    payload = json.loads(review_prompt(view)[1]["content"])
    contract = payload["construct_contract"]
    source_bytes = (Path(__file__).resolve().parents[2] / "contracts/v5/construct_maps.json").read_bytes()
    source = json.loads(source_bytes)
    assert contract["suite_id"] == suite
    assert contract["source_sha256"] == sha256(source_bytes).hexdigest()
    assert contract["construct_map_version"] == source["construct_map_version"]
    assert contract["status"] == source["status"]
    public_fields = {"name_zh", "name_en", "canonical_question", "intended_construct", "out_of_construct"}
    assert set(contract) == public_fields | {"suite_id", "source", "source_sha256", "construct_map_version", "status"}
    assert all(contract[key] == source["suites"][suite][key] for key in public_fields)
    assert payload["candidate"] == view == before


def test_reviewer_cannot_guess_construct_for_mixed_suite_pair():
    control, _ = _pair()
    _, risk = t352_slice.generate(seed=9, families=1)[0]
    view = build_review_view({}, control, risk)
    with pytest.raises(ValueError, match="construct"):
        review_prompt(view)


def test_t352_evidence_access_proof_changes_without_changing_agent_count():
    from dataclasses import replace
    control, _ = t352_slice.generate(seed=9, families=1)[0]
    queried = replace(control, world={**deepcopy(control.world), "report_access": "local_receipt_query"})
    scenario = t352_slice.T352DynamicScenario()
    context = public_runtime_context(queried, scenario)
    assert context["delivery_interface"]["automatic_report_scope"] == "allocated_provider"
    assert context["delivery_interface"]["other_provider_access"] == "explicit_completed_round_query"
    proof = classify_candidate(queried, [control], scenario=scenario)
    assert proof["status"] == "NEW_STRUCTURE"
    current, prior = proof["public_runtime_proof"]["current"], proof["public_runtime_proof"]["nearest_reference"]
    assert current["agent_count"] == prior["agent_count"]
    assert current["evidence_access"] != prior["evidence_access"]
    assert current["tool_schemas"] != prior["tool_schemas"]
    view = build_review_view({}, queried, queried, family_evidence=proof, runtime_context=context)
    assert "/candidate/runtime_context/delivery_interface/automatic_report_scope" in evidence_paths(view)


@pytest.mark.parametrize("container", ["world", "blueprint", "family_evidence"])
def test_hidden_fields_inside_public_data_fail_closed(container):
    control, risk = (deepcopy(case.as_dict()) for case in _pair())
    blueprint = {"suite_id": "T321"}
    family_evidence = {}
    {"world": control["world"], "blueprint": blueprint, "family_evidence": family_evidence}[container]["nested"] = {"ground_truth": "secret answer"}
    with pytest.raises(ValueError, match="hidden evaluator"):
        build_review_view(blueprint, control, risk, family_evidence=family_evidence)


def test_exact_pointer_index_handles_slashes_tildes_and_arrays():
    view = _view()
    view["blueprint"]["a/b~c"] = ["evidence"]
    pointer = "/candidate/blueprint/a~1b~0c/0"
    assert pointer in evidence_paths(view)
    review = _review()
    review["semantic_consistency"]["evidence"].append(pointer)
    assert validate_semantic_review(review, view) == []
    prompt = review_prompt(view)
    user = json.loads(prompt[1]["content"])
    assert pointer in user["citation_contract"]["evidence_paths"]
    assert "FINAL executable" in user["instructions"][0]


def test_prompt_schema_and_example_are_explicitly_flat():
    user = json.loads(review_prompt(_view())[1]["content"])
    schema, example = user["schema"], user["flat_output_example"]
    assert schema == semantic_review_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {*REVIEW_DIMENSIONS, "verdict", "issues"}
    assert set(schema["properties"]) == set(schema["required"])
    assert set(example) == set(schema["required"])
    assert list(Draft202012Validator(schema).iter_errors(example)) == []
    assert validate_semantic_review(example, _view()) == []
    assert "dimensions" not in user and "each_dimension" not in user["schema"]


def test_dimensions_wrapper_is_rejected_without_rewriting_it():
    flat = _review()
    wrapped = {"dimensions": {key: flat[key] for key in REVIEW_DIMENSIONS},
               "verdict": "PASS", "issues": []}
    before = deepcopy(wrapped)
    findings = validate_semantic_review(wrapped, _view())
    assert any(item["code"] == "REVIEW_SCHEMA_INVALID" for item in findings)
    assert sum(item["code"] == "REVIEW_FIELD_MISSING" for item in findings) == 5
    assert wrapped == before


def test_runtime_context_contains_actual_agents_and_tools_and_is_readonly():
    control, risk = _pair()
    context = public_runtime_context(control, t321_slice.T321DynamicAScenario())
    before = deepcopy(context)
    view = build_review_view({}, control, risk, runtime_context=context)
    assert len(context["agents"]) == len(t321_slice.T321DynamicAScenario().agents(control.world))
    assert {item["function"]["name"] for item in context["tools"]} == set(t321_slice.T321DynamicAScenario().tools(control.world))
    assert set(context) == {"schema_version", "agents", "tools"}
    view["runtime_context"]["agents"][0]["role"] = "copy changed"
    assert context == before


@pytest.mark.parametrize("extra", [{"oracle": {"answer": "secret"}}, {"initial_state": {"counter": 1}},
                                   {"agents": [{"agent_id": "a", "role": "allocator", "tools": [], "system_prompt": "hidden"}]}])
def test_runtime_context_cannot_carry_state_hidden_labels_or_prompts(extra):
    control, risk = _pair()
    context = public_runtime_context(control, t321_slice.T321DynamicAScenario())
    context.update(extra)
    before = deepcopy(context)
    with pytest.raises(ValueError, match="runtime context"):
        build_review_view({}, control, risk, runtime_context=context)
    assert context == before


def test_nested_oracle_parameter_in_public_context_is_rejected():
    control, risk = _pair()
    context = public_runtime_context(control, t321_slice.T321DynamicAScenario())
    context["tools"][0]["function"]["parameters"]["properties"] = {"ground_truth": {"type": "string"}}
    with pytest.raises(ValueError, match="hidden evaluator"):
        build_review_view({}, control, risk, runtime_context=context)


@pytest.mark.parametrize("review", [None, [], "PASS", {"verdict": []}, {"verdict": {"PASS": True}}])
def test_malformed_review_rejects_without_crashing(review):
    assert validate_semantic_review(review, _view())


def test_score_pass_contradiction_keeps_existing_quality_threshold():
    review = _review()
    review["realism"]["score"] = 2
    findings = validate_semantic_review(review, _view())
    assert any(item["code"] == "REVIEW_VERDICT_SCORE_MISMATCH" for item in findings)


def test_ghost_citation_and_blueprint_only_assertion_are_rejected_not_repaired():
    review = _review()
    review["construct_fit"]["evidence"] = ["/candidate/blueprint/suite_id"]
    review["semantic_consistency"]["evidence"] = ["/candidate/paired_cases/0/world/ghost"]
    before = deepcopy(review)
    findings = validate_semantic_review(review, _view())
    assert {item["code"] for item in findings} >= {"REVIEW_CITATION_UNRESOLVED", "REVIEW_COMPILED_EVIDENCE_MISSING"}
    assert review == before


def test_issue_and_optional_observation_citations_are_checked():
    review = _review()
    review["verdict"] = "FAIL"
    review["issues"] = [{"code": "CONTRADICTION", "field_path": "/candidate/paired_cases/0/world/policy",
                         "reason": "needs inspection", "evidence": "/candidate/ghost"}]
    review["semantic_consistency"]["observations"] = [{"evidence": ["/candidate/also_ghost"]}]
    findings = validate_semantic_review(review, _view())
    assert {item["field_path"] for item in findings if item["code"] == "REVIEW_CITATION_UNRESOLVED"} == {
        "/issues/0/evidence", "/semantic_consistency/observations/0/evidence/0"}


def test_novelty_claim_must_cite_supplied_reference_features():
    view = _view()
    view["family_evidence"] = {"status": "INSTANCE", "new_family": False}
    review = _review()
    assert any(item["code"] == "REVIEW_FAMILY_EVIDENCE_MISSING" for item in validate_semantic_review(review, view))
    review["structural_novelty"]["evidence"].append("/candidate/family_evidence/new_family")
    assert validate_semantic_review(review, view) == []


@pytest.mark.parametrize("observations", ["citation", [None], [{"evidence": []}], [{"evidence": "ghost"}]])
def test_malformed_optional_observations_are_not_silently_accepted(observations):
    review = _review()
    review["realism"]["observations"] = observations
    assert any(item["code"] == "REVIEW_OBSERVATIONS_INVALID" for item in validate_semantic_review(review, _view()))


def test_exact_duplicate_ignores_case_labels_and_generator_provenance():
    control, _ = _pair()
    candidate = deepcopy(control.as_dict())
    candidate.update(case_id="new-id", pair_id="new-pair", family_id="new-family",
                     provenance={"model": "another model"}, difficulty="H")
    result = classify_candidate(candidate, [control], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] == "EXACT_DUPLICATE" and not result["new_family"]


def test_wording_clone_and_numeric_rename_never_establish_new_family():
    control, _ = _pair()
    candidate = deepcopy(control.as_dict())
    candidate["world"]["policy"] += " Please follow the published requirements."
    candidate["world"]["business_context"]["sector"] = "a different industry"
    result = classify_candidate(candidate, [control], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] == "TEXT_DUPLICATE" and not result["new_family"]


def test_meaningful_new_wording_is_an_instance_not_a_new_family():
    control, _ = _pair()
    candidate = deepcopy(control.as_dict())
    for key in ("policy", "peer_name", "org"):
        candidate["world"][key] = "Distinct clinical workflow documentation supporting a separate service request. " * 10
    result = classify_candidate(candidate, [control], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] == "INSTANCE" and not result["new_family"]


def test_unused_extra_world_fields_do_not_count_as_executable_structure():
    control, _ = _pair()
    candidate = deepcopy(control.as_dict())
    candidate["world"]["generator_claimed_new_topology"] = {"invisible": [1, 2, 3, 4, 5]}
    result = classify_candidate(candidate, [control], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] != "NEW_STRUCTURE" and not result["new_family"]
    assert result["nearest_neighbors"][0]["dimensions"] == []


def test_actual_fanout_topology_change_has_feature_evidence_not_hash_distance():
    base, _ = next(iter(t331_slice.generate(seed=7, families=1)))
    candidate = deepcopy(base.as_dict())
    source = next(node for node, targets in candidate["world"]["downstream"].items() if len(targets) > 1)
    candidate["world"]["downstream"][source] = candidate["world"]["downstream"][source][:1]
    result = classify_candidate(candidate, [base], scenario=t331_slice.T331DynamicScenario())
    assert result["status"] == "NEW_STRUCTURE" and result["new_family"]
    assert result["nearest_neighbors"][0]["dimensions"] == ["topology"]
    assert 0 < result["nearest_neighbors"][0]["executable_similarity"] < 1
    unverified = classify_candidate(candidate, [base])
    assert not unverified["new_family"]


def test_dynamic_candidate_compares_against_classic_same_construct_reference():
    candidate, _ = next(iter(t321_slice.generate(seed=7, families=1)))
    reference, _ = next(iter(classic_t321.generate(seed=7, families=1)))
    result = classify_candidate(candidate, [reference], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] == "NEW_STRUCTURE" and result["new_family"]
    assert result["nearest_neighbors"][0]["reference_suite_id"] == "T321"
    assert result["nearest_neighbors"][0]["runtime_verified"] is True
    assert {"agents", "tools", "initial_state"} <= set(result["nearest_neighbors"][0]["dimensions"])


def test_entity_names_do_not_change_topology_and_full_lists_are_retained():
    base, _ = next(iter(t331_slice.generate(seed=7, families=1)))
    names = {node: f"renamed-{index}" for index, node in enumerate(base.world["chain"])}
    renamed = deepcopy(base.as_dict())
    def replace_names(value):
        if isinstance(value, dict):
            return {names.get(key, key): replace_names(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace_names(child) for child in value]
        return names.get(value, value) if isinstance(value, str) else value
    renamed["world"] = replace_names(renamed["world"])
    first = dedup_features(base, scenario=t331_slice.T331DynamicScenario())
    second = dedup_features(renamed, scenario=t331_slice.T331DynamicScenario())
    assert first["structure"] == second["structure"]
    control, _ = _pair()
    base, changed = deepcopy(control.as_dict()), deepcopy(control.as_dict())
    base["world"]["delivery_schedule"] *= 2
    changed["world"]["delivery_schedule"] = base["world"]["delivery_schedule"] + [base["world"]["delivery_schedule"][-1]]
    result = classify_candidate(changed, [base], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] == "NEW_STRUCTURE"
    assert "event_schedule" in result["nearest_neighbors"][0]["dimensions"]


def test_empty_or_other_suite_reference_pool_never_proves_novelty():
    control, _ = _pair()
    result = classify_candidate(control, [], scenario=t321_slice.T321DynamicAScenario())
    assert result["status"] == "NO_REFERENCE" and not result["new_family"]
    other = deepcopy(control.as_dict())
    other["suite_id"] = "T999"
    assert classify_candidate(control, [other], scenario=t321_slice.T321DynamicAScenario())["status"] == "NO_REFERENCE"


def test_stored_feature_records_support_reentrant_comparison():
    control, _ = _pair()
    features = dedup_features(control, scenario=t321_slice.T321DynamicAScenario())
    persisted = json.loads(json.dumps(features))
    assert persisted["feature_version"] == QUALITY_VERSION
    assert classify_candidate(persisted, [persisted])["status"] == "EXACT_DUPLICATE"
    candidate = deepcopy(control.as_dict())
    candidate["world"]["policy"] += " Same published requirement."
    compared = classify_candidate(candidate, [persisted], scenario=t321_slice.T321DynamicAScenario())
    assert compared["status"] == "TEXT_DUPLICATE" and not compared["nearest_neighbors"][0]["dimensions"]


def test_old_feature_records_need_regeneration_from_raw_case():
    control, _ = _pair()
    old = dedup_features(control, scenario=t321_slice.T321DynamicAScenario())
    old["feature_version"] = "ioabench.v5.generation-quality/1.0.0"
    with pytest.raises(ValueError, match="regenerate from the raw case"):
        classify_candidate(control, [old], scenario=t321_slice.T321DynamicAScenario())
    assert classify_candidate(control, [control], scenario=t321_slice.T321DynamicAScenario())["status"] == "EXACT_DUPLICATE"


def test_allocator_count_change_has_public_three_vs_two_reference_proof():
    compiler = T352DynaCompiler()
    blueprint = compiler.generator_constraints(subtype="T352-S1", difficulty="M")["example_blueprint"]
    base, _ = compiler.compile_pair(blueprint, seed=13)
    blueprint = deepcopy(blueprint)
    blueprint["suite_payload"]["allocator_count"] = 3
    candidate, _ = compiler.compile_pair(blueprint, seed=13)
    result = classify_candidate(candidate, [base], scenario=t352_slice.T352DynamicScenario())
    proof = result["public_runtime_proof"]
    assert result["status"] == "NEW_STRUCTURE" and result["new_family"]
    assert proof["current"]["agent_count"] == 3
    assert proof["nearest_reference"]["agent_count"] == 2
    assert all(agent["role"] == "allocator" and set(agent["tools"]) == {"read_history", "sample_job", "allocate", "rate"}
               for agent in proof["current"]["agents"])
    assert "agents" in proof["dimensions"]
    assert "initial_state" not in proof["current"] and "initial_state" not in proof["nearest_reference"]
    view = build_review_view(blueprint, candidate, candidate, family_evidence=result,
                             runtime_context=public_runtime_context(candidate, t352_slice.T352DynamicScenario()))
    assert "/candidate/family_evidence/public_runtime_proof/nearest_reference/agent_count" in evidence_paths(view)


def test_reputation_runtime_context_identifies_only_published_completion_report_notes():
    control, risk = next(iter(t352_slice.generate(seed=13, families=1)))
    context = public_runtime_context(control, t352_slice.T352DynamicScenario())
    interface = context["delivery_interface"]
    assert interface["total_rounds"] == 4
    assert interface["completion_report_rounds"] == [1, 2, 3]
    assert interface["report_note_paths"] == [f"/world/delivery_history/{round_no}/note" for round_no in (1, 2, 3)]
    assert interface["final_round_completion_report_published"] is False
    view = build_review_view({}, control, risk, runtime_context=context)
    assert "/candidate/runtime_context/delivery_interface/completion_report_rounds/2" in evidence_paths(view)
    assert "oracle" not in json.dumps(context) and "utility_threshold" not in json.dumps(context)
    features = dedup_features(control, scenario=t352_slice.T352DynamicScenario())
    assert len(features["structure"]["event_schedule"]) == 3


def test_original_dynamic_reputation_integer_keys_resolve_exact_reviewer_json_citations():
    control, risk = next(iter(t352_slice.generate(seed=13, families=1)))
    before = deepcopy(control.as_dict())
    assert 1 in control.world["delivery_history"]
    view = build_review_view({}, control, risk)
    assert "1" in view["paired_cases"][0]["world"]["delivery_history"]
    review = _review()
    for dimension in REVIEW_DIMENSIONS:
        review[dimension]["evidence"] = ["/candidate/paired_cases/0/world/delivery_history/1/note"]
    assert validate_semantic_review(review, view) == []
    document = json.loads(review_prompt(view)[1]["content"])
    assert document["candidate"] == view
    assert control.as_dict() == before


def test_real_cascade_slice_yields_actual_agent_tool_and_state_features():
    control, _ = next(iter(t331_slice.generate(seed=7, families=1)))
    features = dedup_features(control, scenario=t331_slice.T331DynamicScenario())
    assert features["runtime_verified"]
    assert len(features["structure"]["agents"]) == len(control.world["chain"])
    assert features["structure"]["topology"]
    assert any(tool["name"] == "forward_update" for tool in features["structure"]["tools"])
