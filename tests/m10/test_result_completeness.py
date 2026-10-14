import json
from pathlib import Path

from ioabench.cli import _validate_run


def test_mock_run_has_one_terminal_result_per_work_unit() -> None:
    root = Path(__file__).parents[2]
    run = root / "data" / "runs" / "mock-v1"
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    assert len(results) == 1620
    terminal = {"VALID", "INVALID_RUN", "UNSUPPORTED", "RETRYABLE_INFRA_FAILURE", "FAILED", "CANCELLED"}
    assert all(record.get("eligibility") in terminal for record in results.values())
    assert all(record.get("status") == "COMPLETED" for record in results.values())


def test_run_validation_writes_machine_readable_completeness(tmp_path: Path) -> None:
    run = tmp_path / "data" / "runs" / "r"
    (run / "manifest").mkdir(parents=True)
    (run / "replay").mkdir()
    replay = {"content_sha256": "sha", "timeline": [{"event_type": "task.completed"}]}
    (run / "replay" / "w.json").write_text(json.dumps(replay), encoding="utf-8")
    (run / "results.json").write_text(json.dumps({"w": {"status": "COMPLETED", "eligibility": "VALID", "replay": "replay/w.json", "replay_sha256": "sha"}}), encoding="utf-8")
    (run / "manifest" / "r.json").write_text(json.dumps({"run_id": "r", "tested_model": {"model_id": "mock"}, "benchmark": {}}), encoding="utf-8")

    assert _validate_run("r", tmp_path) == 0
    report = json.loads((run / "completeness.json").read_text(encoding="utf-8"))
    assert report["status"] == "VALID"
    assert report["work_units"]["valid"] == 1
    assert report["replay"]["hash_matches"] == 1
