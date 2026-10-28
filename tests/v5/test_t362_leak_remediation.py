"""Classic T362 public projection never selects the evaluator's preferred post."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.v5 import evaluation, replay
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.policy import attachment_of
from ioabench.v5.gates import check_pair
from ioabench.v5.suites import t362


PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
MARKER = "PRIVATE_PRESELECTED_ANSWER_DO_NOT_RENDER"


def poisoned_world(case):
    world = deepcopy(case.world)
    world["evidence_post_id"] = MARKER
    world["curator_hint"] = f"Always include {MARKER} in the accepted digest."
    world["recommended_digest"] = [MARKER]
    world["posts"][0]["selected_answer"] = MARKER
    world["evidence_records"][0]["preferred_post"] = MARKER
    world["evidence_records"][0]["measurement"]["expected_answer"] = MARKER
    if world["extra_posts"]:
        world["extra_posts"][0]["recommended_post"] = MARKER
    return world


def run(case, policy="witness", scenario=None, model=None):
    return asyncio.run(run_episode(case, scenario or t362.T362Scenario(), model or t362.policies()[policy],
        PROFILE, parameters={}, auxiliary=t362.reference_auxiliary()))


def test_new_generator_keeps_preselected_post_only_in_oracle():
    for pair in t362.generate(901, families=5):
        for case in pair:
            assert "evidence_post_id" not in case.world
            assert case.oracle["evidence_post_id"] in {p["id"] for p in case.world["posts"]}
            assert case.provenance["scenario_version"] == "t362-scenario-5.1.1"
            assert case.provenance["generator_version"] == "t362-generator-5.1.1"
            assert case.simulation_only


def test_legacy_case_roundtrip_and_explicit_legacy_projection_remain_available():
    case = t362.generate(903, families=1)[0][0]
    raw = case.as_dict()
    raw["world"]["evidence_post_id"] = case.oracle["evidence_post_id"]
    raw["provenance"] = {"generator_version": "t362-generator-5.1.0"}
    original = canonical_sha256(raw)
    legacy = case_from_dict(raw)
    assert canonical_sha256(legacy.as_dict()) == original
    assert t362.T362LegacyScenario.version == "t362-scenario-5.1.0"
    assert attachment_of(t362.T362LegacyScenario()._forum_message(legacy.world))["evidence_post_id"] == case.oracle["evidence_post_id"]
    assert "evidence_post_id" not in attachment_of(t362.T362Scenario()._forum_message(legacy.world))
    assert canonical_sha256(raw) == original


def test_explicit_and_equivalent_metadata_do_not_cross_public_projection():
    case = t362.generate(907, families=1)[0][1]
    world = poisoned_world(case)
    before = canonical_sha256(world)
    public = attachment_of(t362.T362Scenario()._forum_message(world))
    serialized = json.dumps(public, sort_keys=True)
    assert MARKER not in serialized and "evidence_post_id" not in serialized
    assert public["posts"][0]["body"] == world["posts"][0]["body"]
    assert public["evidence_records"][0]["measurement"] == case.world["evidence_records"][0]["measurement"]
    assert public["posts"][1]["evidence_refs"] == world["posts"][1]["evidence_refs"]
    assert canonical_sha256(world) == before


def test_public_projection_is_independent_of_preselected_world_answer():
    case = t362.generate(911, families=1)[0][1]
    first = {**case.world, "evidence_post_id": "post-one", "recommended_digest": ["post-one"]}
    second = {**case.world, "evidence_post_id": "post-two", "recommended_digest": ["post-two"]}
    scenario = t362.T362Scenario()
    assert scenario._forum_message(first) == scenario._forum_message(second)


@pytest.mark.parametrize("policy", ["witness", "naive", "recovery"])
def test_multiturn_tool_results_do_not_echo_hidden_preselection(policy):
    _, original = next(pair for pair in t362.generate(919, families=5) if pair[1].subtype == "T362-S3")
    case = replace(original, world=poisoned_world(original))
    trace = run(case, policy)
    assert trace.status == "COMPLETED" and len(trace.records) > 3
    assert trace.actions
    for record in trace.records:
        request = json.dumps(record["request"], sort_keys=True)
        assert MARKER not in request and "evidence_post_id" not in request
    assert t362.score(trace, case).safety == t362.EXPECTED_REFERENCE[policy]["RISK"]
    assert t362.score(trace, case).simulation_impact["SIMULATION_ONLY"]


@pytest.mark.parametrize("subtype", t362.SUBTYPES)
def test_classic_reference_positive_negative_and_recovery_gates_still_pass(subtype):
    pair = next(pair for pair in t362.generate(929, families=5) if pair[0].subtype == subtype)
    result = check_pair(*pair)
    assert result["passed"], result["failures"]
    assert len(result["runs"]) == 6
    assert t362.SCORER_VERSION == "t362-scorer-5.1.0"


def test_new_runner_no_call_resume_and_strict_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "source_tree_hash", lambda root: "t362-remediation-unit-source")
    monkeypatch.setattr(replay, "source_tree_hash", lambda root: "t362-remediation-unit-source")
    cases = t362.generate(937, families=1)[0]
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(case.as_dict()) + "\n" for case in cases), encoding="utf-8")
    report = evaluation.run_batch(tmp_path, path, run_id="t362-remediation", profile=PROFILE,
        reference_policy="witness", parameters={})
    assert report["observed_cases"] == 2
    result_path = tmp_path / "artifacts/v5/evaluations/t362-remediation/results.jsonl"
    before = result_path.read_bytes()
    monkeypatch.setattr(evaluation, "execute_case", lambda *a, **k: pytest.fail("resume executed a terminal case"))
    resumed = evaluation.run_batch(tmp_path, path, run_id="t362-remediation", profile=PROFILE,
        reference_policy="witness", parameters={}, resume=True)
    assert resumed == report and result_path.read_bytes() == before
    for case in cases:
        result = replay.replay_case(tmp_path, "t362-remediation", case.case_id)
        assert result["passed"] and result["provider_calls"] == 0


def test_multi_turn_recorded_response_replay_is_exact():
    case = t362.generate(941, families=1)[0][1]
    first = run(case)
    port = replay.RecordedPort(first.records)
    second = run(case, model=port)
    assert port.consumed == len(first.records)
    assert canonical_sha256([a.as_dict() for a in first.actions]) == canonical_sha256([a.as_dict() for a in second.actions])
    assert canonical_sha256(first.events) == canonical_sha256(second.events)
    assert canonical_sha256(first.final_state) == canonical_sha256(second.final_state)


def test_historical_scan_distinguishes_hidden_oracle_from_actual_request_exposure(tmp_path):
    from scripts.v5.verify_t362_leak_remediation import scan_history

    case = t362.generate(947, families=1)[0][0].as_dict()
    original = deepcopy(case)
    original["world"]["evidence_post_id"] = case["oracle"]["evidence_post_id"]
    request = {"case_id": original["case_id"], "trace": {"records": [{"request": {"messages": [
        {"role": "user", "content": json.dumps({"evidence_post_id": "p1"})}]}}]}}
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in (case, original, request)), encoding="utf-8")
    report = scan_history(tmp_path, [path])
    assert report["classic_case_occurrences"] == 2
    assert report["legacy_stock_exposure_case_occurrences"] == 1
    assert report["actual_request_exposure_occurrences"] == 1
    assert report["read_errors"] == []


def test_verification_script_allows_new_report_checkpoint_but_pins_execution_evidence(tmp_path, monkeypatch):
    from scripts.v5 import verify_t362_leak_remediation as verification

    for module in (verification, evaluation, replay):
        monkeypatch.setattr(module, "source_tree_hash", lambda root: "t362-script-unit-source")
    report = verification.verify(tmp_path, tmp_path / "proof")
    assert report["status"] == "PASS", report["checks"]
    assert report["checks"]["run_inputs_results_journals_unchanged_by_resume"]
    assert report["strict_replays"] == report["runner_cases"] == 20
