import json
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]


def test_construct_remediation_queue_and_state_are_consistent():
    queue = yaml.safe_load((ROOT / "state/WORK_QUEUE.yaml").read_text(encoding="utf-8"))
    state = yaml.safe_load((ROOT / "state/PROJECT_STATE.yaml").read_text(encoding="utf-8"))
    validation = json.loads((ROOT / "state/WORK_QUEUE_VALIDATION.json").read_text(encoding="utf-8"))
    items = {item["id"]: item for item in queue["items"]}
    assert len(items) == len(queue["items"]) == queue["summary"]["task_count"] == validation["task_count"] == state["work_queue_task_count"]
    assert queue["version"] == validation["work_queue_version"] == state["work_queue_version"]
    assert validation["milestone_counts"] == dict(Counter(item["milestone"] for item in items.values()))
    assert all(dependency in items for item in items.values() for dependency in item["depends_on"])
    assert set(queue["milestones"]) == set(validation["milestone_counts"])
    assert all(items[item]["status"] == "done" for item in ("CIG-00", "CIG-01", "CIG-02", "CIG-CONTRACT", "CIG-T311"))
    assert items["CIG-REST-16"]["status"] == "done"
    assert items["CIG-R6-ENTRY"]["status"] == "blocked"
    # lifecycle status advances as milestones close; assert progression, not a
    # frozen historical literal
    assert state["status"] in {"per_suite_frozen_datasets_complete_awaiting_provider_key_for_online_campaign",
                               "scientific_closure_and_canonical_binding",
                               "scientific_closure_complete",
                               "v4_corrective_release_and_strict_formal_campaign",
                               "v4_corrective_campaign_final_delivery_complete"}
    assert set(state["in_progress"]) >= set(state["next"]) - {None}
    assert "V2-A07-PHASE-A-FINAL-ACCEPTANCE" in items["CIG-R6-ENTRY"]["depends_on"]
    for gate in ("CIG-OFFLINE-GATE", "CIG-REST-16"):
        assert items[gate]["current_acceptance"] == "superseded-for-current-acceptance"
    assert state["scientific_status"]["t311_dataset_2_0_0"] == "ACCEPTED_FOR_V2_USE"
    assert all(items[item]["status"] == "done" for item in ("CIG-WAVE2-T313", "CIG-WAVE2-T323"))
    # The legacy boolean flag was superseded by explicit acceptance gates during
    # the v3.2 closure; assert the authoritative artifacts exist and pass.
    impl_gate = json.loads((ROOT / "artifacts/gates/BENCHMARK_IMPLEMENTATION_ACCEPTANCE_V3_2_FINAL.json").read_text(encoding="utf-8"))
    assert impl_gate["pass"] is True and impl_gate["verdict"] == "PASS"
    phase_a = json.loads((ROOT / "artifacts/gates/PHASE_A_V2_FINAL_ACCEPTANCE.json").read_text(encoding="utf-8"))
    assert phase_a.get("overall_pass") is True or phase_a.get("pass") is True

def test_construct_dispatch_uses_suite_specific_runtimes():
    from ioabench.runtime.construct_runtime import run_construct_baseline
    suites = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
              "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")
    results = {suite: run_construct_baseline(ROOT, suite, "safe") for suite in suites}
    assert set(results) == set(suites)
    assert all(result["replay"]["timeline"] for result in results.values())
    assert all(result["replay"]["model_records"] for result in results.values())

def test_all_suite_baselines_are_action_sensitive_without_provider_calls():
    from ioabench.runtime.construct_runtime import run_construct_baseline
    suites = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
              "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")
    for suite in suites:
        safe = run_construct_baseline(ROOT, suite, "safe")["score"]
        naive = run_construct_baseline(ROOT, suite, "naive")["score"]
        alternative = run_construct_baseline(ROOT, suite, "alternative")["score"]
        recovery = run_construct_baseline(ROOT, suite, "recovery")["score"]
        assert safe["outcome_class"] == "EARLY_SAFE" and safe["task_utility"] is True
        assert naive["outcome_class"] in {"UNSAFE_ACTION", "FULL_FAILURE"}
        assert alternative["outcome_class"] not in {"UNSAFE_ACTION", "FULL_FAILURE"}
        assert recovery["outcome_class"] in {"LATE_RECOVERY", "EARLY_SAFE"}


def test_construct_baseline_cli_is_offline_and_separate_from_formal_runs(tmp_path, monkeypatch):
    from ioabench import cli

    monkeypatch.setattr(cli, "ROOT", ROOT)
    output = tmp_path / "construct-baseline.json"
    assert cli._construct_baseline("T311", "safe", str(output)) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "construct-baseline"
    assert payload["provider_calls"] == 0
    assert payload["suites"]["T311"]["score"]["outcome_class"] == "EARLY_SAFE"
    assert not (tmp_path / "data" / "runs").exists()
