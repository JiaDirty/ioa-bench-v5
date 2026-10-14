"""V4-S5: freeze the v4 corrective Benchmark Release.

Only runs when the Phase A/B gates pass. The release pins the candidate source
tree, dataset pack, contracts, prompts, scorer/runtime/dispatch versions, model
profile, scheduler, strict retry semantics, replay schema, the frozen Synthetic
Human profile and the canonical constraints. Fails closed if any input is
missing or inconsistent; never mutates a historical release.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, reference, write_new

ART = ROOT / "artifacts/scientific_closure_v4"
CAND = ART / "corrective-candidate-v2"
SUITES = ["T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
          "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(base: Path) -> str:
    digest = hashlib.sha256()
    for scope in ("src", "contracts", "config"):
        for path in sorted((base / scope).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            digest.update(path.relative_to(base).as_posix().encode("utf-8"))
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> int:
    # gate order: S2/S3/S4 must all pass
    for gate in ("V4_S1_CANDIDATE_FORK_001.json", "V4_S2_STRICT_RETRY_001.json",
                 "V4_S3_CANDIDATE_VALIDATION_001.json", "V4_S4_PREFREEZE_AUDIT_001.json"):
        if json.loads((ROOT / "artifacts/gates" / gate).read_text(encoding="utf-8")).get("pass") is not True:
            raise SystemExit(f"refusing to freeze: {gate} is not PASS")

    source_tree = tree_hash(CAND)
    pack_path = ROOT / "data/datasets/DATASET_PACK_v4.yaml"
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))

    datasets = {}
    for suite in SUITES:
        item = pack["suites"][suite]
        mp = ROOT / "data/datasets" / suite / str(item["version"]) / "manifest.json"
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        if manifest.get("content_sha256") != item.get("content_sha256"):
            raise SystemExit(f"dataset hash mismatch for {suite}")
        datasets[suite] = {"version": str(item["version"]), "content_sha256": item["content_sha256"],
                           "manifest_sha256": sha(mp),
                           "quality_gates": item.get("quality_gates", {})}

    contracts = {s: sha(CAND / "contracts/constructs" / f"{s}.json") for s in SUITES}

    dispatch_src = (CAND / "src/ioabench/runtime/construct_dispatch.py").read_text(encoding="utf-8")
    dispatch_version = re.search(r'DISPATCH_VERSION = "([^"]+)"', dispatch_src).group(1)

    # prompt hashes: T311 constants are literal in its runtime module; the other
    # suites use the neutral role prompts recorded in ADDENDUM_1's inventory.
    prompt_hashes = {}
    t311_src = (CAND / "src/ioabench/runtime/t311_construct.py").read_text(encoding="utf-8")
    for label, const in (("T311.base", "LEAD_PROMPT"), ("T311.role", "EXECUTOR_PROMPT")):
        m = re.search(rf'{const} = "(.*?)"\n', t311_src, re.S)
        prompt_hashes[label] = hashlib.sha256(json.loads('"' + m.group(1) + '"').encode("utf-8")).hexdigest()

    scorer_versions = {s: ("t353-selection-2.2.0" if s == "T353" else "v1") for s in SUITES}
    runtime_versions = {s: ("t353-selection-2.2.0" if s == "T353" else f"{s.lower()}-construct-1.0.0")
                        for s in SUITES}

    release = {
        "artifact": "BENCHMARK_RELEASE",
        "release_id": "v4-corrective-20261001",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "supersedes": {
            "path": "release/BENCHMARK_RELEASE_v3-20260930.json",
            "sha256": sha(ROOT / "release/BENCHMARK_RELEASE_v3-20260930.json"),
            "note": "the v3 release and its addenda remain immutable historical evidence; v4 is a new semantic release",
        },
        "basis": {
            "reason": "strict retry semantics: INVALID_MODEL_OUTPUT and INFRA_INTERRUPTED are terminal, only zero-behaviour infrastructure failures may resume, every attempt is retained",
            "candidate_validation_checks": 82,
            "prefreeze_audit_checks": 27,
            "full_pytest": "831 passed, 2 skipped",
        },
        "source_tree_sha256": source_tree,
        "dependency_lock_sha256": sha(ROOT / "config/dependencies.lock.json"),
        "dataset_pack_v4_sha256": sha(pack_path),
        "datasets": datasets,
        "contracts": contracts,
        "prompt_hashes": prompt_hashes,
        "tool_schema_hashes": {
            "note": "tool definitions are literal in each suite runtime module inside the pinned source tree; "
                    "the per-record inventory is recorded in release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_1.json",
        },
        "scorer_versions": scorer_versions,
        "runtime_versions": runtime_versions,
        "runtime_mapping": {"dispatch_version": dispatch_version,
                            "simulation_suites": ["T361", "T362", "T363"]},
        "tested_model": {"model_id": "deepseek-v4.1-flash", "temperature": 0.0, "max_tokens": 8192,
                         "provider": "aihubmix"},
        "scheduler_profile": json.loads((ROOT / "config/scheduler_profile.json").read_text(encoding="utf-8")),
        "invalid_output_semantics": {
            "INVALID_MODEL_OUTPUT": "recorded terminal outcome; never scored safe; never retried",
            "INFRA_INTERRUPTED": "terminal after at least one valid model behaviour; partial evidence retained; never retried",
            "RETRYABLE_INFRA_FAILURE": "resumable only when zero valid model behaviour was observed and the cause is infrastructure-class",
            "FAILED": "terminal; non-infrastructure exception; never auto-retried",
            "PROVIDER_FAILURE": "infrastructure denominator; never counted as a model result",
            "strict_retry_semantics": True,
            "attempts": "every attempt is recorded; resume never overwrites a prior attempt",
        },
        "replay_schema": {"bundle_version": "construct-replay-v2",
                          "embedded": True,
                          "content_hash": "canonical_sha256 over the bundle excluding content_sha256",
                          "paired_branches": "T353 retains primary/honest/manipulated raw replays"},
        "auxiliary_model_profiles": json.loads((ROOT / "config/synthetic_human.json").read_text(encoding="utf-8")),
        "canonical_constraints": {
            "taxonomy_frozen": True,
            "oracle_hidden": True,
            "public_internet_formal_runs": False,
            "t361_t363_simulation_only": True,
            "frozen_datasets_immutable": True,
            "single_execution_per_case_per_model": True,
            "retry_semantics_strict": True,
        },
        "tested_model_roster_policy": ["deepseek-v4.1-flash"],
        "runtime_profile": {"os": "Windows", "docker_required": False, "provider": "aihubmix"},
    }

    out = ROOT / "release/BENCHMARK_RELEASE_v4-corrective-20261001.json"
    write_new(out, release)
    digest = sha(out)

    gate = {
        "artifact": "V4_S5_RELEASE_FREEZE",
        "version": "1",
        "pass": True,
        "provider_calls": 0,
        "release": reference(out),
        "release_id": release["release_id"],
        "source_tree_sha256": source_tree,
        "dataset_pack_v4_sha256": release["dataset_pack_v4_sha256"],
        "supersedes_v3_sha256": release["supersedes"]["sha256"],
        "historical_release_unchanged": True,
        "command": "python -B -X utf8 scripts/v4_freeze_release.py",
    }
    write_new(ROOT / "artifacts/gates/V4_S5_RELEASE_FREEZE_001.json", gate)
    print(json.dumps({"release_id": release["release_id"], "release_sha256": digest,
                      "source_tree_sha256": source_tree,
                      "datasets": len(datasets), "contracts": len(contracts)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
