"""V4-S6: freeze the 18 formal Run Manifests, all bound to the v4 release.

Each manifest pins the same release_id, release_sha256 and source_tree_sha256,
plus the per-suite dataset version/hash, scorer/runtime versions, model profile
and strict-retry semantics. Manifests are frozen BEFORE execution so a run can
never be published without a pre-committed identity.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, reference, write_new

SUITES = ["T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
          "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    release_path = ROOT / "release/BENCHMARK_RELEASE_v4-corrective-20261001.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release_sha = sha(release_path)
    release_id = release["release_id"]
    source_tree = release["source_tree_sha256"]

    registry = {"artifact": "V4_RUN_MANIFEST_REGISTRY", "version": "1", "provider_calls": 0,
                "release": {"release_id": release_id, "release_sha256": release_sha,
                            "source_tree_sha256": source_tree},
                "manifests": {}, "runs": {}}

    out_dir = ROOT / "data/runs/_v4_manifests"
    out_dir.mkdir(parents=True, exist_ok=True)

    for suite in SUITES:
        ds = release["datasets"][suite]
        # v4 run ids are distinct from every historical directory
        run_id = f"deepseek-v4.1-flash-{suite}-{ds['version']}-v4-formal"
        manifest = {
            "schema_version": "1.0",
            "run_id": run_id,
            "profile": "local-v1",
            "tested_model": {"provider": "aihubmix", "model_id": "deepseek-v4.1-flash",
                             "parameters": {"temperature": 0.0, "max_tokens": 8192}},
            "benchmark": {
                "suite_versions": {suite: ds["version"]},
                "dataset_versions": {suite: ds["version"]},
                "dataset_hashes": {suite: ds["content_sha256"]},
                "dataset_pack": "DATASET_PACK_V4",
                "scorer_versions": {suite: release["scorer_versions"][suite]},
                "base_prompt_versions": {suite: "neutral-v1"},
            },
            "runtime": {
                "runtime_version": release["runtime_versions"][suite],
                "dispatch_version": release["runtime_mapping"]["dispatch_version"],
                "execution_concurrency": release["scheduler_profile"]["profiles"]["tested_model"]["concurrency"],
                "dependency_lock_sha256": release["dependency_lock_sha256"],
                "git_sha": "sha256:" + source_tree,
                "simulation_only": suite in {"T361", "T362", "T363"},
            },
            "release": {
                "release_id": release_id,
                "release_sha256": release_sha,
                "source_tree_sha256": source_tree,
                "dataset_pack_v4_sha256": release["dataset_pack_v4_sha256"],
                "strict_retry_semantics": True,
            },
        }
        path = out_dir / f"{run_id}.manifest.json"
        write_new(path, manifest)
        registry["manifests"][suite] = reference(path)
        registry["runs"][suite] = {"run_id": run_id, "dataset_version": ds["version"],
                                   "dataset_sha256": ds["content_sha256"],
                                   "simulation_only": suite in {"T361", "T362", "T363"}}

    # every manifest must bind the identical release triple
    bound = {(m["release"]["release_id"], m["release"]["release_sha256"], m["release"]["source_tree_sha256"])
             for m in (json.loads((ROOT / r["path"]).read_text(encoding="utf-8")) for r in registry["manifests"].values())}
    registry["all_bind_same_release"] = len(bound) == 1 and bound.pop() == (release_id, release_sha, source_tree)
    registry["suite_count"] = len(registry["manifests"])

    reg_path = ROOT / "artifacts/scientific_closure_v4/run-manifest-registry-001.json"
    write_new(reg_path, registry)

    gate = {
        "artifact": "V4_S6_RUN_MANIFEST_FREEZE",
        "version": "1",
        "pass": registry["all_bind_same_release"] and registry["suite_count"] == 18,
        "provider_calls": 0,
        "release": reference(release_path),
        "suite_count": registry["suite_count"],
        "all_bind_same_release": registry["all_bind_same_release"],
        "run_ids": {s: r["run_id"] for s, r in registry["runs"].items()},
        "frozen_before_execution": True,
        "command": "python -B -X utf8 scripts/v4_freeze_run_manifests.py",
        "evidence": [reference(reg_path)],
    }
    write_new(ROOT / "artifacts/gates/V4_S6_RUN_MANIFEST_FREEZE_001.json", gate)
    print(json.dumps({"suite_count": registry["suite_count"],
                      "all_bind_same_release": registry["all_bind_same_release"],
                      "sample_run_id": registry["runs"]["T311"]["run_id"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
