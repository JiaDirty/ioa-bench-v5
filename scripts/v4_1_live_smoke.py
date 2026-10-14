"""Phase D smoke for the v4.1.1 integration Release.

The smoke is deliberately non-canonical: it resolves the exact tested model,
executes three deterministic T311 cases through the strict dispatcher, and
checks AttemptJournal/replay/release evidence. It never writes frozen Dataset
files or formal results.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "release/BENCHMARK_RELEASE_v4.1.1-corrective-integration-20261002.json"
GATE_PATH = ROOT / "artifacts/scientific_closure_v4/live-smoke/V4_1_S8_LIVE_SMOKE.json"
MODEL = "deepseek-v4.1-flash"
SUITE = "T311"
VERSION = "2.0.0"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_cases() -> list[dict]:
    dataset = ROOT / "data/datasets" / SUITE / VERSION / "cases.jsonl"
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    chosen = []
    for difficulty, condition in (("easy", "CONTROL"), ("medium", "RISK"), ("hard", "CONTROL")):
        chosen.append(next(case for case in cases
                           if case["difficulty"] == difficulty
                           and case["provenance"]["condition"] == condition))
    return chosen


def validate_results(results: list[dict], release: dict, release_sha: str) -> dict:
    terminal = {"COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED", "FAILED"}
    model_records = sum(len((item.get("replay") or {}).get("model_records", [])) for item in results)
    checks = {
        "three_cases": len(results) == 3,
        "all_terminal": all(item.get("status") in terminal for item in results),
        "no_retryable": all(item.get("status") != "RETRYABLE_INFRA_FAILURE" for item in results),
        "attempt_one_only": all(item.get("attempt_no") == 1 for item in results),
        "replay_present": all(isinstance(item.get("replay"), dict) for item in results),
        "model_records_6_to_12": 6 <= model_records <= 12,
        "release_id": release["release_id"] == "v4.1.1-corrective-integration-20261002",
        "release_sha256": len(release_sha) == 64,
    }
    return {"checks": checks, "pass": all(checks.values()), "model_records": model_records}


async def execute_smoke() -> dict:
    from ioabench.config.loader import load_workspace_env
    from ioabench.models import AIHubMixAdapter
    from ioabench.runtime.construct_dispatch import execute_construct_case_strict

    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    release_sha = sha256(RELEASE_PATH)
    expected_tree = release["source_tree_sha256"]
    from ioabench.runtime.full_manifest import source_tree_hash
    if source_tree_hash(ROOT) != expected_tree:
        raise SystemExit("workspace source tree does not match v4.1.1 Release")

    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve(MODEL)
    if profile.model_id != MODEL:
        raise SystemExit(f"provider resolved an unexpected model: {profile.model_id}")

    run_id = f"{MODEL}-{SUITE}-v4.1-smoke-{time.strftime('%Y%m%d-%H%M%S')}"
    results = []
    for case in select_cases():
        results.append(await execute_construct_case_strict(
            ROOT, SUITE, case, adapter, profile, run_id=run_id))

    run_dir = ROOT / "data/runs" / run_id
    manifest = {
        "artifact": "V4_1_1_LIVE_SMOKE_MANIFEST",
        "run_id": run_id,
        "release": {"release_id": release["release_id"], "release_sha256": release_sha,
                    "source_tree_sha256": expected_tree},
        "tested_model": {"provider": profile.provider, "requested_model_id": MODEL,
                         "resolved_model_id": profile.model_id},
        "suite": SUITE, "dataset_version": VERSION,
        "case_ids": [item["case_id"] for item in results],
        "formal_canonical": False, "provider_calls": 1 + sum(len((item.get("replay") or {}).get("model_records", [])) for item in results),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "smoke-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "smoke-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_results(results, release, release_sha)
    return {"artifact": "V4_1_1_LIVE_SMOKE", "pass": validation["pass"], "provider_calls": manifest["provider_calls"],
            "release": manifest["release"], "run_id": run_id, "manifest": manifest,
            "validation": validation, "results": [{"case_id": r["case_id"], "status": r["status"],
                                                       "attempt_no": r.get("attempt_no"),
                                                       "model_records": len((r.get("replay") or {}).get("model_records", []))}
                                                      for r in results]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if GATE_PATH.exists():
        raise SystemExit(f"refusing to overwrite existing smoke gate: {GATE_PATH}")
    report = asyncio.run(execute_smoke())
    output = Path(args.output) if args.output else ROOT / "artifacts/scientific_closure_v4/live-smoke/V4_1_1_S8_LIVE_SMOKE_ATTEMPT_001.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    if report["pass"]:
        with GATE_PATH.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"pass": report["pass"], "provider_calls": report["provider_calls"],
                      "run_id": report["run_id"], "output": str(output)}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
