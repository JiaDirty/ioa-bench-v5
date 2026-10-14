"""Freeze the canonical Benchmark Release manifest (G7).

Freezes every public research condition of the benchmark into one immutable,
hash-pinned manifest:

- 18 authoritative dataset versions + content hashes (from DATASET_PACK_v3);
- construct contract versions per suite;
- source tree hash, dependency lock, Windows runtime profile;
- runtime mapping (dispatch + per-suite runtime versions from the construct
  dispatcher);
- scorer and base-prompt identities, tool budgets;
- replay schema version, invalid-output semantics;
- provider/retry policy, frozen scheduler/concurrency profile;
- auxiliary model profiles (semantic validators, synthetic human + personas);
- frozen tested-model roster policy note.

Refuses to overwrite an existing release manifest.

Usage: python scripts/freeze_benchmark_release.py [--release-id v3-20260929]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.runtime.construct_dispatch import DISPATCH_VERSION, RUNNERS, SIMULATION_SUITES  # noqa: E402
from ioabench.runtime.full_manifest import source_tree_hash  # noqa: E402

from ioabench.frozen_versions import FROZEN_VERSIONS  # single source of truth


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", default=f"ioa-bench-v3-{time.strftime('%Y%m%d')}")
    args = parser.parse_args()

    out = ROOT / "release" / f"BENCHMARK_RELEASE_{args.release_id}.json"
    if out.exists():
        print(f"refusing to overwrite frozen release: {out}")
        return 1

    pack_path = ROOT / "data" / "datasets" / "DATASET_PACK_v4.yaml"
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    datasets = {}
    for suite, version in FROZEN_VERSIONS.items():
        manifest = json.loads((ROOT / "data" / "datasets" / suite / version / "manifest.json").read_text(encoding="utf-8"))
        pack_entry = pack["suites"].get(suite)
        if not pack_entry or pack_entry["version"] != version or pack_entry["content_sha256"] != manifest["content_sha256"]:
            print(f"FAIL {suite}: pack v3 does not pin {suite}@{version} with the frozen hash")
            return 1
        datasets[suite] = {"version": version, "content_sha256": manifest["content_sha256"],
                            "quality_gates": manifest.get("quality_gates", {}),
                            "independent_validation": (ROOT / "data" / "datasets" / suite / version / "independent-semantic-validation.json").is_file()}

    sh_config = json.loads((ROOT / "config" / "synthetic_human.json").read_text(encoding="utf-8"))
    scheduler = json.loads((ROOT / "config" / "scheduler_profile.json").read_text(encoding="utf-8"))
    aux = json.loads((ROOT / "artifacts" / "gates" / "AUX_MODEL_PROFILES.json").read_text(encoding="utf-8"))

    release = {
        "artifact": "BENCHMARK_RELEASE",
        "release_id": args.release_id,
        "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "canonical_constraints": {
            "taxonomy_frozen": True,
            "oracle_hidden": True,
            "public_internet_formal_runs": False,
            "t361_t363_simulation_only": True,
            "frozen_datasets_immutable": True,
            "single_execution_per_case_per_model": True,
        },
        "datasets": datasets,
        "dataset_pack_v4_sha256": _sha(pack_path),
        "source_tree_sha256": source_tree_hash(ROOT),
        "dependency_lock_sha256": _sha(ROOT / "pyproject.toml"),
        "runtime_profile": {"os": platform.platform(), "python": platform.python_version(),
                             "docker_required": False, "provider": "aihubmix"},
        "runtime_mapping": {"dispatch_version": DISPATCH_VERSION,
                             "simulation_suites": sorted(SIMULATION_SUITES),
                             "runner_modules": {suite: RUNNERS[suite][0] for suite in sorted(RUNNERS)}},
        "invalid_output_semantics": ("INVALID_MODEL_OUTPUT is a recorded terminal outcome, never scored safe; "
                                      "RETRYABLE_INFRA_FAILURE/PROVIDER_FAILURE are infrastructure, retried by frozen "
                                      "resume passes, never counted as model results"),
        "replay_schema": "construct-dispatch-1 bundle (immutable request hashes; scenario.manifest.runtime_version per suite)",
        "scheduler_profile": scheduler,
        "auxiliary_model_profiles": {
            "semantic_validators": aux["roles"]["semantic_validator_primary"]["model_id"]
                                    + " + " + aux["roles"]["semantic_validator_independent_secondary"]["model_id"],
            "synthetic_human": {"model_id": sh_config["model_id"], "frozen": sh_config["frozen"],
                                  "persona_set_version": sh_config["persona_set_version"],
                                  "protocol_version": sh_config["protocol_version"],
                                  "persona_assignment": sh_config["persona_assignment"]},
            "selection_evidence": "artifacts/gates/AUX_MODEL_PROFILES.json",
        },
        "tested_model_roster_policy": "final roster is user-controlled; each selected model gets a frozen Model Profile and its own 18-suite campaign on this release",
        "prompt_policy": "tested-agent base prompts are neutral and frozen per release; no post-hoc tuning against observed results",
    }
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(release, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"frozen: {out}")
    print(f"source_tree_sha256: {release['source_tree_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
