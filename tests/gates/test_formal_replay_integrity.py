import json
from pathlib import Path

from ioabench.replay import audit_run

def test_mock_formal_replay_integrity() -> None:
    root = Path(__file__).parents[2]
    run = root / "data" / "runs" / "mock-v1"
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    sample = list(results.values())[::180]
    assert len(sample) == 9
    for record in sample:
        replay = run / record["replay"]
        value = json.loads(replay.read_text(encoding="utf-8"))
        assert value["content_sha256"] == record["replay_sha256"]
        assert "oracle_payload" not in json.dumps(value["scenario"].get("agents", []), ensure_ascii=False)
        assert value["timeline"]


def test_historical_formal_replay_is_not_scientifically_valid() -> None:
    root = Path(__file__).parents[2]
    report = audit_run(root, "deepseek-v4.1-flash-v1")
    assert report["status"] == "FAIL"
    assert report["audited_valid_units"] == 1620
    assert any("case is absent" in failure["reason"] or "model-visible" in failure["reason"] for failure in report["failures"])
