from pathlib import Path
import json

from scripts.run_t311_trial import run_trial


def test_t311_trial_is_offline_and_replayable(tmp_path):
    summary = run_trial(Path(__file__).parents[2], tmp_path / "trial", count=2)
    assert summary["provider_calls"] == 0
    assert summary["formal_dataset"] is False
    outcomes = {(item["policy"], item["outcome"]) for item in summary["results"]}
    assert {("safe", "EARLY_SAFE"), ("naive", "FULL_FAILURE"), ("alternative", "EARLY_SAFE"), ("recovery", "LATE_RECOVERY")} <= outcomes
    assert len(list((tmp_path / "trial" / "replays").glob("*/replay/*.json"))) == 8


def test_t311_trial_uses_generated_registry_world_and_replay_audit(tmp_path):
    summary = run_trial(Path(__file__).parents[2], tmp_path / "trial", count=1)
    assert summary["trial_id"] == "T311-construct-trial-2.0.0"
    case = json.loads((tmp_path / "trial" / "cases.json").read_text(encoding="utf-8"))[0]
    assert len(case["registry_cards"]) == 4
    assert case["registry_cards"][0]["agent_id"] == "executor-0001"
    assert case["oracle_payload"]["valid_agents"] == ["alternate-0001"]
    replay = json.loads(next((tmp_path / "trial" / "replays").glob("*/replay/*.json")).read_text(encoding="utf-8"))
    assert replay["scenario"]["registry_cards"] == case["registry_cards"]
    assert replay["scenario"]["source_records"] == case["source_records"]
    assert all("oracle_payload" not in json.dumps(record["request"]) for record in replay["model_records"])
