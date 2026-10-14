"""Verify the v4.1.4 workspace and pre-provider integration state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v5"
BASELINE = ROOT / "artifacts/scientific_closure_v3_2/baseline.json"
RELEASE = ROOT / "release/BENCHMARK_RELEASE_v4.1.4-corrective-integration-20261002.json"
EXPECTED_PROMOTION = {
    "src/ioabench/cli.py",
    "src/ioabench/core/types.py",
    "src/ioabench/runtime/batch.py",
    "src/ioabench/runtime/construct_dispatch.py",
    "src/ioabench/runtime/discovery_selection.py",
    "src/ioabench/runtime/full_manifest.py",
    "src/ioabench/runtime/run_gates.py",
    "src/ioabench/runtime/scientific_io.py",
    "src/ioabench/suites/t353/construct_scoring.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for directory in ("src", "contracts", "config"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def audit() -> dict:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    baseline_changes = {
        relative for relative, expected in baseline["files"].items()
        if not (ROOT / relative).is_file() or sha256(ROOT / relative) != expected
    }
    authoritative_differences = []
    for directory in ("src", "contracts", "config"):
        candidate_files = {p.relative_to(CANDIDATE).as_posix(): p for p in (CANDIDATE / directory).rglob("*")
                           if p.is_file() and "__pycache__" not in p.parts}
        workspace_files = {p.relative_to(ROOT).as_posix(): p for p in (ROOT / directory).rglob("*")
                           if p.is_file() and "__pycache__" not in p.parts}
        for relative in sorted(set(candidate_files) | set(workspace_files)):
            left, right = candidate_files.get(relative), workspace_files.get(relative)
            if left is None or right is None or sha256(left) != sha256(right):
                authoritative_differences.append(relative)
    current_tree = tree_hash(ROOT)
    candidate_tree = tree_hash(CANDIDATE)
    release_sha = sha256(RELEASE)
    integration = release["execution_integration"]
    tool_hashes = integration["execution_tool_sha256"]
    mismatched_tools = [relative for relative, expected in tool_hashes.items()
                        if not (ROOT / relative).is_file() or sha256(ROOT / relative) != expected]
    manifest_dir = ROOT / integration["prefrozen_manifest_directory"]
    manifest_paths = sorted(manifest_dir.glob("*.manifest.json"))
    manifest_failures = []
    run_ids = []
    for path in manifest_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        run_ids.append(payload.get("run_id"))
        binding = payload.get("release", {})
        if (binding.get("release_id") != release["release_id"]
                or binding.get("release_sha256") != release_sha
                or binding.get("source_tree_sha256") != release["source_tree_sha256"]):
            manifest_failures.append(path.name)
    historical_runs = [ROOT / "data" / "runs" / run_id.removesuffix("-v4.1-formal")
                       for run_id in run_ids]
    historical_runs = [path.with_name(path.name + "-formal") for path in historical_runs]
    formal_runs = [ROOT / "data" / "runs" / run_id for run_id in run_ids]
    smoke_gate = ROOT / integration["live_smoke_gate"]
    checks = {
        "baseline_changes_are_exact_promotion": baseline_changes == EXPECTED_PROMOTION,
        "workspace_equals_frozen_candidate": not authoritative_differences,
        "workspace_tree_matches_release": current_tree == release["source_tree_sha256"],
        "candidate_tree_matches_release": candidate_tree == release["source_tree_sha256"],
        "execution_tools_match_release": not mismatched_tools,
        "eighteen_prefrozen_manifests": len(manifest_paths) == 18,
        "manifests_bind_release": not manifest_failures,
        "historical_runs_preserved": len(historical_runs) == 18 and all(path.is_dir() for path in historical_runs),
        "no_successor_formal_runs_yet": not any(path.exists() for path in formal_runs),
        "no_successor_smoke_gate_yet": not smoke_gate.exists(),
    }
    return {
        "artifact": "V4_1_4_RUNTIME_INTEGRATION_AUDIT",
        "provider_calls": 0,
        "pass": all(checks.values()),
        "checks": checks,
        "historical_baseline_file_count": len(baseline["files"]),
        "expected_promoted_files": sorted(EXPECTED_PROMOTION),
        "actual_baseline_changes": sorted(baseline_changes),
        "unexpected_baseline_changes": sorted(baseline_changes - EXPECTED_PROMOTION),
        "authoritative_tree_differences": authoritative_differences,
        "workspace_source_tree_sha256": current_tree,
        "candidate_source_tree_sha256": candidate_tree,
        "release_source_tree_sha256": release["source_tree_sha256"],
        "release_id": release["release_id"],
        "release_sha256": release_sha,
        "mismatched_execution_tools": mismatched_tools,
        "prefrozen_manifest_count": len(manifest_paths),
        "manifest_binding_failures": manifest_failures,
        "existing_successor_formal_runs": [path.name for path in formal_runs if path.exists()],
        "successor_smoke_gate_exists": smoke_gate.exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    report = audit()
    if args.output:
        path = ROOT / args.output
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
