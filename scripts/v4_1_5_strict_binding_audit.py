"""Phase G — v4.1.5 strict binding audit across all 18 suites (read-only).

Aggregates the per-suite Phase F validation into a single audit artifact.  For a
v4-native campaign every suite must reach ``STRICT_BINDING``; anything less is
listed as a blocker and the aggregate verdict fails.

Canonical aggregation (Phase C) may consume only suites this audit marks
``canonical_accepted``.

Usage:
    python scripts/v4_strict_binding_audit.py --output <path>
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "release/BENCHMARK_RELEASE_v4.1.5-corrective-integration-20261002.json"
SUITES = [f"T3{a}{b}" for a in "123456" for b in "123"]


def _load_validator():
    spec = importlib.util.spec_from_file_location("v4_1_5_validate_run", ROOT / "scripts/v4_1_5_validate_run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v4_1_5_validate_run"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--runs-dir")
    ap.add_argument("--manifest-dir")
    args = ap.parse_args()

    validator = _load_validator()
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    release_sha = hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest()

    runs_dir = pathlib.Path(args.runs_dir) if args.runs_dir else validator.RUNS_DIR
    manifest_dir = pathlib.Path(args.manifest_dir) if args.manifest_dir else validator.MANIFEST_DIR

    reports = []
    for suite in SUITES:
        rep = validator.validate_suite(release, suite, runs_dir=runs_dir,
                                       manifest_dir=manifest_dir, release_sha=release_sha)
        reports.append(rep)

    strict = [r for r in reports if r["binding_level"] == "STRICT_BINDING"]
    counts: dict[str, int] = {}
    for r in reports:
        counts[r["binding_level"]] = counts.get(r["binding_level"], 0) + 1

    blockers = [
        {"suite": r["suite"], "run_id": r["run_id"], "binding_level": r["binding_level"],
         "failures": [f["name"] for f in r["failures"]]}
        for r in reports if not r["canonical_accepted"]
    ]

    all_strict = len(strict) == len(SUITES)
    payload = {
        "artifact": "V4_1_5_STRICT_BINDING_AUDIT",
        "release_id": release["release_id"],
        "release_sha256": release_sha,
        "source_tree_sha256": release["source_tree_sha256"],
        "tested_model_roster": release["tested_model_roster_policy"],
        "historical_runs_consumed": 0,
        "provider_calls": 0,
        "binding_level_counts": counts,
        "strict_count": len(strict),
        "total_suites": len(SUITES),
        "canonical_suites": [r["suite"] for r in reports if r["canonical_accepted"]],
        "blockers": blockers,
        "suites": reports,
        "verdict": "STRICT_18_OF_18" if all_strict else "NOT_STRICT",
        "pass": all_strict,
        "version": "1",
    }

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: payload[k] for k in
                      ("artifact", "release_id", "strict_count", "total_suites",
                       "binding_level_counts", "verdict", "pass")},
                     ensure_ascii=False, indent=2))
    return 0 if all_strict else 1


if __name__ == "__main__":
    sys.exit(main())
