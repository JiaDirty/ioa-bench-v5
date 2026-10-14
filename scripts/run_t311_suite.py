"""Run one frozen T311 dataset through the construct-valid executor."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.runtime.t311_baselines import T311Baseline
from ioabench.runtime.t311_construct import execute_t311, freeze_t311_offline_result
from ioabench.runtime.t311_fixture import build_t311_case_from_skeleton


def load_cases(dataset: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    actual = canonical_sha256({"manifest": {**manifest, "content_sha256": None}, "cases": cases})
    if actual != manifest.get("content_sha256"):
        raise ValueError("T311 dataset content hash mismatch")
    return manifest, cases


async def run(args: argparse.Namespace) -> dict:
    dataset = ROOT / "data" / "datasets" / "T311" / args.dataset
    dataset_manifest, records = load_cases(dataset)
    run_id = args.run_id
    output = ROOT / "data" / "runs" / run_id
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    if args.model == "mock":
        model = T311Baseline(args.policy)
        profile = ModelProfile("mock", f"t311-{args.policy}", {"tools": True}, {})
    else:
        adapter = AIHubMixAdapter()
        profile = await adapter.resolve(args.model)
        model = adapter
    results = {}
    for record in records:
        case = build_t311_case_from_skeleton(record)
        result = await execute_t311(ROOT, case, model, profile, run_id=run_id)
        case_root = output / "cases" / case["case_id"]
        replay_path = freeze_t311_offline_result(result, case_root, case)
        results[case["case_id"]] = {
            "status": result["status"],
            "eligibility": result["eligibility"],
            "score": result["score"],
            "replay": str(replay_path.relative_to(output)),
            "replay_sha256": result["replay"]["content_sha256"],
            "difficulty": record["difficulty"],
            "condition": record["provenance"]["condition"],
        }
    manifest = {
        "schema_version": "t311-suite-run-v1",
        "run_id": run_id,
        "suite": "T311",
        "dataset_version": dataset_manifest["version"],
        "dataset_sha256": dataset_manifest["content_sha256"],
        "tested_model": {"provider": profile.provider, "model_id": profile.model_id, "parameters": {"temperature": 0.0, "max_tokens": 1024}},
        "runtime": {"source_tree_sha256": source_tree_hash(ROOT), "runtime": "T311-construct-1.0.0"},
        "formal_dataset": args.formal,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {
        "run_id": run_id,
        "suite": "T311",
        "dataset_version": dataset_manifest["version"],
        "case_count": len(results),
        "eligibility": {status: sum(item["eligibility"] == status for item in results.values()) for status in sorted({item["eligibility"] for item in results.values()})},
        "outcomes": {outcome: sum(item["score"]["outcome_class"] == outcome for item in results.values()) for outcome in sorted({item["score"]["outcome_class"] for item in results.values()})},
        "provider_calls": sum(len(json.loads((output / item["replay"]).read_text(encoding="utf-8")).get("model_records", [])) for item in results.values()),
        "formal_dataset": args.formal,
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="2.0.0")
    parser.add_argument("--model", default="mock")
    parser.add_argument("--policy", choices=("safe", "naive", "alternative", "recovery"), default="safe")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
