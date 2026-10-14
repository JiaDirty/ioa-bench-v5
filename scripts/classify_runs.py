"""Classify every existing formal run against the authoritative benchmark (G8).

Walks data/runs, audits each run's dataset identity, unit completeness,
terminal-state semantics and manifest, and assigns exactly one classification:

- VALID_RESEARCH_RESULT: terminal, complete, on the authoritative frozen
  dataset version for its suite (canonical status is decided separately at
  release freeze).
- VALID_BUT_DIFFERENT_BENCHMARK_RELEASE: terminal and complete on a superseded
  dataset version - scientifically valid, not canonical for the current pack.
- DEVELOPMENT_EXPLORATORY: development-era execution evidence (mock runs,
  probes, superseded exploratory passes).
- INVALIDATED: formally invalidated by a documented defect (e.g. truncated
  candidate_id collision run).
- ORPHAN_INCOMPLETE: no results / partial evidence left behind.

Usage: python scripts/classify_runs.py [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TERMINAL = {"COMPLETED", "INVALID_MODEL_OUTPUT"}

# authoritative dataset versions (same map as reconcile_state / pack v3)
from ioabench.frozen_versions import FROZEN_VERSIONS  # single source of truth

# documented invalidation events (state/CHANGELOG.md + V2_CHECKPOINT)
INVALIDATION_NOTES = {
    "deepseek-v4.1-flash-T312-2.0.0-formal": "truncated 30/90-unit run: candidate_id collision collapsed 90 cases to 30 executable units; superseded by the 2.2.0 rerun",
    "deepseek-v4.1-flash-T313-2.1.0-formal": "candidate_id collision era: only 30/90 payloads executable; superseded by the 2.3.0 rerun",
    "deepseek-v4.1-flash-T321-v2-formal": "pre-collision-fix era run on 2.x-era dataset; superseded by the 2.2.0 formal run",
}


def classify_run(run_dir: Path) -> dict:
    name = run_dir.name
    if name == "manifests":  # manifest store, not a run
        return {"run_id": name, "classification": "DEVELOPMENT_EXPLORATORY",
                "reason": "immutable manifest store directory, not a run"}
    entry: dict = {"run_id": name}
    results_path = run_dir / "results.json"
    manifest_candidates = sorted((run_dir / "manifest").glob("*.json")) if (run_dir / "manifest").is_dir() else []
    entry["has_manifest"] = bool(manifest_candidates)
    manifest = json.loads(manifest_candidates[0].read_text(encoding="utf-8")) if manifest_candidates else None

    if not results_path.is_file():
        if name in INVALIDATION_NOTES:
            entry["classification"] = "INVALIDATED"
            entry["reason"] = INVALIDATION_NOTES[name] + " (result files no longer present; superseding run retained)"
            return entry
        entry["classification"] = "DEVELOPMENT_EXPLORATORY" if "pilot" in name else "ORPHAN_INCOMPLETE"
        entry["reason"] = "no results.json; pilot/execution evidence only" if "pilot" in name else "run directory has no results"
        return entry

    results = json.loads(results_path.read_text(encoding="utf-8"))
    entry["units"] = len(results)
    statuses: dict[str, int] = {}
    for value in results.values():
        status = value.get("status") or "?"
        statuses[status] = statuses.get(status, 0) + 1
    entry["statuses"] = statuses
    all_terminal = bool(results) and all(v.get("status") in TERMINAL for v in results.values())
    suite = next((str(v.get("suite")) for v in results.values() if v.get("suite")), None)
    entry["suite"] = suite
    entry["dataset_version"] = (manifest or {}).get("benchmark", {}).get("dataset_versions", {}).get(suite) if manifest else None

    if name in INVALIDATION_NOTES:
        entry["classification"] = "INVALIDATED"
        entry["reason"] = INVALIDATION_NOTES[name]
        return entry

    if "pilot" in name:
        entry["classification"] = "DEVELOPMENT_EXPLORATORY"
        entry["reason"] = "B5 pilot evidence (12-case sample), not a formal run"
        return entry

    model_id = str((manifest or {}).get("tested_model", {}).get("model_id") or ("mock" if name.startswith("mock") else "unknown"))
    entry["tested_model"] = model_id
    if model_id == "mock" or name.startswith("mock") or name.startswith("campaign-test"):
        entry["classification"] = "DEVELOPMENT_EXPLORATORY"
        entry["reason"] = "mock-model engineering verification, never a model research result"
        return entry

    version = str(entry["dataset_version"] or "")
    if not version.startswith("2."):
        entry["classification"] = "DEVELOPMENT_EXPLORATORY"
        entry["reason"] = (f"executed on pre-remediation construct semantics (dataset {suite}@{version or 'unknown'}); "
                           "the CIG construct rebuild superseded those runtimes - retained as engineering evidence")
        return entry

    if suite is None or suite not in FROZEN_VERSIONS:
        entry["classification"] = "DEVELOPMENT_EXPLORATORY"
        entry["reason"] = "not an 18-suite formal run (development-era execution evidence)"
        return entry

    if not all_terminal:
        entry["classification"] = "ORPHAN_INCOMPLETE"
        entry["reason"] = f"non-terminal statuses present: {statuses}"
        return entry

    authoritative = FROZEN_VERSIONS[suite] == entry["dataset_version"]
    if authoritative:
        entry["classification"] = "VALID_RESEARCH_RESULT"
        entry["reason"] = (f"{suite}@{entry['dataset_version']}: {entry['units']} units all terminal "
                           f"({statuses.get('COMPLETED', 0)} COMPLETED / {statuses.get('INVALID_MODEL_OUTPUT', 0)} INVALID_MODEL_OUTPUT); "
                           "manifest present" if entry["has_manifest"] else "manifest missing")
        entry["canonical"] = False  # decided at release freeze (G7), never by this audit
    else:
        entry["classification"] = "VALID_BUT_DIFFERENT_BENCHMARK_RELEASE"
        entry["reason"] = (f"complete and terminal on {suite}@{entry['dataset_version']}, "
                           f"not the authoritative version {FROZEN_VERSIONS[suite]}")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    runs_root = ROOT / "data" / "runs"
    entries = []
    for run_dir in sorted(runs_root.iterdir()):
        if run_dir.is_dir():
            try:
                entries.append(classify_run(run_dir))
            except Exception as exc:  # noqa: BLE001 - classification must not die on one bad directory
                entries.append({"run_id": run_dir.name, "classification": "ORPHAN_INCOMPLETE",
                                "reason": f"audit error: {type(exc).__name__}: {exc}"[:200]})

    summary: dict[str, int] = {}
    for entry in entries:
        summary[entry["classification"]] = summary.get(entry["classification"], 0) + 1
    report = {"artifact": "RUN_CLASSIFICATION",
              "audited_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "authoritative_versions": FROZEN_VERSIONS,
              "summary": summary,
              "canonical_policy": "canonical status is assigned only by the Benchmark Release freeze (G7); VALID and CANONICAL are tracked separately",
              "runs": entries}
    out = ROOT / "artifacts" / "gates" / "RUN_CLASSIFICATION.json"
    print(json.dumps(summary, indent=1))
    if args.write:
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
