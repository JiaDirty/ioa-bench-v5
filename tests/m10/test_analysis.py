import json
from pathlib import Path

from ioabench.analysis.metrics import analyze_run, write_metrics


def test_analysis_keeps_safety_and_utility_separate(tmp_path: Path) -> None:
    run = tmp_path / "data" / "runs" / "r"
    run.mkdir(parents=True)
    (run / "results.json").write_text(json.dumps({"w": {"suite": "T311", "eligibility": "VALID", "score": {"verification_rate": 1.0, "task_success": 1.0, "outcome_class": "EARLY_SAFE"}}}), encoding="utf-8")
    summary = analyze_run(tmp_path, "r")
    assert "safety_metrics" in summary["suites"]["T311"]
    assert summary["suites"]["T311"]["task_utility"]["task_success"] == 1.0
    assert summary["suites"]["T311"]["breakdowns"]["difficulty"]["UNKNOWN"]["valid_count"] == 1
    assert summary["suites"]["T311"]["uncertainty"]["task_success_wilson_95"]
    assert write_metrics(summary, tmp_path / "metrics").exists()


def test_analysis_recovers_utility_from_replay(tmp_path: Path) -> None:
    run = tmp_path / "data" / "runs" / "r"
    run.mkdir(parents=True)
    replay = run / "replay.json"
    replay.write_text(json.dumps({"final_utility": {"task_success": True, "model_calls": 2, "tool_calls": 1}, "model_records": [{"usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}}], "timeline": []}), encoding="utf-8")
    (run / "results.json").write_text(json.dumps({"w": {"suite": "T333", "eligibility": "VALID", "score": {}, "replay": "replay.json"}}), encoding="utf-8")
    summary = analyze_run(tmp_path, "r")
    suite = summary["suites"]["T333"]
    assert suite["task_utility"]["task_success"] == 1.0
    assert suite["task_utility"]["source_counts"] == {"replay.final_utility": 1}
    assert suite["efficiency"]["total_tokens"]["mean"] == 14.0
    assert suite["cost"]["status"] == "NOT_RECORDED"


def test_analysis_reads_model_id_from_nonlegacy_manifest(tmp_path: Path) -> None:
    run_id = "formal-pack-v2-r5"
    run = tmp_path / "data" / "runs" / run_id
    (run / "manifest").mkdir(parents=True)
    (tmp_path / "artifacts" / "runs" / "deepseek-v4.1-flash").mkdir(parents=True)
    (run / "manifest" / f"{run_id}.json").write_text(
        json.dumps({"tested_model": {"model_id": "deepseek-v4.1-flash"}}),
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "runs" / "deepseek-v4.1-flash" / "model-resolution.json").write_text(
        json.dumps({"pricing": {"input": 1.0, "output": 2.0, "cache_read": 0.5}}),
        encoding="utf-8",
    )
    replay = run / "replay.json"
    replay.write_text(
        json.dumps({"final_utility": {"task_success": True}, "model_records": [{"usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}}], "timeline": []}),
        encoding="utf-8",
    )
    (run / "results.json").write_text(
        json.dumps({"w": {"suite": "T311", "eligibility": "VALID", "score": {}, "replay": "replay.json"}}),
        encoding="utf-8",
    )
    summary = analyze_run(tmp_path, run_id)
    assert summary["suites"]["T311"]["cost"]["status"] == "ESTIMATED_FROM_LIVE_CATALOG"
