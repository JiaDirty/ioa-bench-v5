"""Re-score recorded episodes into a new evidence directory without provider calls.

Strict historical replay still requires its original source. This command instead verifies
identical requests, actions, events, state and monitors, then reports old/new scoring separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.evaluation import atomic_json, safe_id, writer_lock
from ioabench.v5.replay import reanalyse_case
from ioabench.v5.reporting import build_report, write_report


def analyse(root: Path, run_id: str, out: Path) -> dict:
    safe_id(run_id)
    directory = root / "artifacts/v5/evaluations" / run_id
    sources = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
               for name in ("manifest.json", "cases.jsonl", "results.jsonl")}
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if out.exists():
        raise FileExistsError("reanalysis output exists; choose a new versioned path")
    out.mkdir(parents=True)
    analysis_source = source_tree_hash(ROOT)
    atomic_json(out / "CHECKPOINT.json", {"status": "IN_PROGRESS", "provider_calls": 0})
    with writer_lock(out):
        reviews = [reanalyse_case(root, run_id, case["case_id"]) for case in manifest["cases"]]
        if not all(review.get("passed") and "result" in review for review in reviews):
            raise ValueError("incomplete original traces; reanalysis rejected")
        if sources != {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in sources}:
            raise ValueError("original evidence changed during reanalysis")
        if source_tree_hash(ROOT) != analysis_source:
            raise ValueError("analysis source changed during reanalysis")
        rows = [review.pop("result") for review in reviews]
        with (out / "results.jsonl").open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        summary = {"schema_version": "ioabench.v5.recorded-reanalysis/1", "run_id": run_id,
                   "evidence_class": "RECORDED_RESPONSE_REANALYSIS_NOT_NEW_ONLINE_RUN",
                   "analysis_source_sha256": analysis_source, "original_source_sha256": manifest["source_sha256"],
                   "original_files": sources, "cases": len(rows), "provider_calls": 0,
                   "original_evidence_unchanged": True, "formal_accepted": False, "case_checks": reviews}
        atomic_json(out / "ANALYSIS.json", summary)
        write_report(build_report(rows, manifest), out / "report")
        atomic_json(out / "CHECKPOINT.json", {"status": "COMPLETED_REANALYSIS_NOT_NEW_ONLINE_RUN",
                                             "cases": len(rows), "provider_calls": 0})
    return {k: v for k, v in summary.items() if k != "case_checks"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyse(ROOT, args.run_id, args.out), ensure_ascii=False, indent=2))
