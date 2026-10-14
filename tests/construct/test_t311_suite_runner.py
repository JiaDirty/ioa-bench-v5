import json
import os
import subprocess
import sys
from pathlib import Path


def test_t311_suite_runner_uses_frozen_dataset_and_writes_replays(tmp_path):
    root = Path(__file__).parents[2]
    run_id = f"t311-suite-runner-test-{os.getpid()}"
    target = root / "data" / "runs" / run_id
    if target.exists():
        raise AssertionError("test run directory already exists")
    completed = subprocess.run(
        [sys.executable, "scripts/run_t311_suite.py", "--dataset", "2.0.0", "--model", "mock", "--run-id", run_id],
        cwd=root, capture_output=True, text=True, check=False,
    )
    try:
        assert completed.returncode == 0, completed.stderr
        summary = json.loads((target / "summary.json").read_text(encoding="utf-8"))
        assert summary["case_count"] == 90
        assert summary["eligibility"] == {"VALID": 90}
        assert (target / "manifest.json").is_file()
    finally:
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        target.rmdir()
