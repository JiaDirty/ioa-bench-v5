import json

from scripts.v5.tf_r3_pilot import unstarted_baseline_tasks


def test_remaining_baseline_excludes_all_attempted_scopes_and_orphan_intents(tmp_path):
    tasks = [{"id": "R3-T362-x" + str(i)} for i in range(1, 7)]
    for scope, candidate in (("old", "R3-T362-x1-R"), ("followup", "R3-T362-x2-R")):
        directory = tmp_path / scope / "ab/candidates" / candidate
        directory.mkdir(parents=True)
        (directory / "MANIFEST.json").write_text("{}", encoding="utf-8")
    ledger = tmp_path / "followup/REQUEST_LEDGER.jsonl"
    ledger.write_text(json.dumps({"event": "REQUEST_INTENT", "request_id": "unknown",
                                  "directory": "ab/candidates/R3-T362-x3-R/model_io"}) + "\n",
                      encoding="utf-8")
    assert unstarted_baseline_tasks(tasks, tmp_path) == tasks[3:]
