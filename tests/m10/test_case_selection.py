import json
from pathlib import Path

from ioabench.analysis.cases import select_cases


def test_case_selection_is_deterministic(tmp_path: Path) -> None:
    run = tmp_path / "data" / "runs" / "r"
    run.mkdir(parents=True)
    records = {"a": {"suite": "T311", "case_id": "c1", "score": {"outcome_class": "EARLY_SAFE"}, "replay": "replay/a.json"}, "b": {"suite": "T312", "case_id": "c2", "score": {"outcome_class": "UNSAFE_ACTION"}, "replay": "replay/b.json"}}
    (run / "results.json").write_text(json.dumps(records), encoding="utf-8")
    assert select_cases(tmp_path, "r") == select_cases(tmp_path, "r")
