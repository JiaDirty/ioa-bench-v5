"""V4-S2b: run one real mock suite through the candidate CLI end to end.

Exercises the production wiring (cli -> BatchRunner -> strict dispatcher ->
AttemptJournal -> checkpoint -> results.json) with the mock model. The
candidate supplies the *code*; the workspace supplies the frozen datasets, so
cli.ROOT is rebound for the run. No network, no provider calls.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("D:/Project/ioa_codex_spec")
CAND = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v2"
RUN_ID = "mock-v4-strict-e2e"
SUITE = "T311"
DATASET = "2.0.0"

sys.path.insert(0, str(CAND / "src"))
os.environ["IOABENCH_CONCURRENCY"] = "1"

from ioabench import cli  # noqa: E402

cli.ROOT = ROOT

run_root = ROOT / "data" / "runs" / RUN_ID
if run_root.exists():
    import shutil
    shutil.rmtree(run_root)

code = cli.main(["run", "--model", "mock", "--suite", SUITE, "--dataset", DATASET, "--run-id", RUN_ID])
print("cli exit:", code)

checkpoint = run_root / "checkpoint.json"
results = run_root / "results.json"
summary = {"artifact": "V4_E2E_MOCK_SUITE", "run_id": RUN_ID, "suite": SUITE,
           "cli_exit": code, "checkpoint_exists": checkpoint.is_file(),
           "results_exists": results.is_file()}
if results.is_file():
    data = json.loads(results.read_text(encoding="utf-8"))
    from collections import Counter
    summary["cases"] = len(data)
    summary["status_counts"] = dict(Counter(v.get("status") for v in data.values()))
    summary["eligibility_counts"] = dict(Counter(str(v.get("eligibility")) for v in data.values()))
    summary["attempts_recorded"] = sum(1 for v in data.values() if isinstance(v.get("attempts"), list) and v["attempts"])
    summary["journals_on_disk"] = len(list((run_root / "attempts").glob("*/*.jsonl"))) if (run_root / "attempts").is_dir() else 0
    sample = next(iter(data.values()))
    summary["sample_attempt"] = sample.get("attempts", [None])[0]
    summary["non_mock_manifest"] = json.loads((run_root / "manifest" / f"{RUN_ID}.json").read_text(encoding="utf-8")).get("tested_model")
print(json.dumps(summary, ensure_ascii=False, indent=1)[:2600])
