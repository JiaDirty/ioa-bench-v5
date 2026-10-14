"""Freeze 18 v4.1.1 Run Manifests before Provider execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "release/BENCHMARK_RELEASE_v4.1.1-corrective-integration-20261002.json"
OUTPUT = ROOT / "data/runs/_v4_1_1_manifests"
REGISTRY = ROOT / "artifacts/scientific_closure_v4/run-manifest-registry-v4.1.1-001.json"
SUITES = [f"T3{a}{b}" for a in "123456" for b in "123"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists() or REGISTRY.exists():
        raise SystemExit("refusing to overwrite frozen v4.1.1 manifests or registry")
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    release_sha = sha256(RELEASE_PATH)
    OUTPUT.mkdir(parents=True)
    registry = {"artifact": "V4_1_1_RUN_MANIFEST_REGISTRY", "version": "1", "provider_calls": 0,
                "release": {"release_id": release["release_id"], "release_sha256": release_sha,
                            "source_tree_sha256": release["source_tree_sha256"]},
                "manifests": {}, "runs": {}}
    for suite in SUITES:
        dataset = release["datasets"][suite]
        run_id = f"deepseek-v4.1-flash-{suite}-{dataset['version']}-v4.1-formal"
        manifest = {
            "schema_version": "1.0", "run_id": run_id, "profile": "local-v1",
            "tested_model": {"provider": "aihubmix", "model_id": "deepseek-v4.1-flash",
                             "parameters": {"temperature": 0.0, "max_tokens": 8192}},
            "benchmark": {"suite_versions": {suite: dataset["version"]},
                          "dataset_versions": {suite: dataset["version"]},
                          "dataset_hashes": {suite: dataset["content_sha256"]},
                          "dataset_pack": "DATASET_PACK_V4",
                          "scorer_versions": {suite: release["scorer_versions"][suite]},
                          "base_prompt_versions": {suite: "neutral-v1"}},
            "runtime": {"runtime_version": release["runtime_versions"][suite],
                        "dispatch_version": release["runtime_mapping"]["dispatch_version"],
                        "execution_concurrency": release["scheduler_profile"]["profiles"]["tested_model"]["concurrency"],
                        "dependency_lock_sha256": release["dependency_lock_sha256"],
                        "git_sha": "sha256:" + release["source_tree_sha256"],
                        "simulation_only": suite in {"T361", "T362", "T363"}},
            "release": {"release_id": release["release_id"], "release_sha256": release_sha,
                        "source_tree_sha256": release["source_tree_sha256"],
                        "dataset_pack_v4_sha256": release["dataset_pack_v4_sha256"],
                        "strict_retry_semantics": True},
        }
        path = OUTPUT / f"{run_id}.manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        registry["manifests"][suite] = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
        registry["runs"][suite] = {"run_id": run_id, "dataset_version": dataset["version"],
                                   "dataset_sha256": dataset["content_sha256"],
                                   "simulation_only": suite in {"T361", "T362", "T363"}}
    registry["suite_count"] = len(registry["manifests"])
    registry["all_bind_same_release"] = True
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"suite_count": 18, "release_sha256": release_sha,
                      "registry_sha256": sha256(REGISTRY), "provider_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
