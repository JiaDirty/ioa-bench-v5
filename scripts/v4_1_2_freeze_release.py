"""Freeze the non-semantic v4.1.2 delivery-integration successor Release."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT
PREVIOUS = ROOT / "release/BENCHMARK_RELEASE_v4.1.1-corrective-integration-20261002.json"
OUTPUT = ROOT / "release/BENCHMARK_RELEASE_v4.1.2-corrective-integration-20261002.json"
TOOLS = (
    "scripts/run_online_campaign.py",
    "scripts/v4_1_2_live_smoke.py",
    "scripts/v4_1_2_validate_run.py",
    "scripts/v4_1_2_strict_binding_audit.py",
    "scripts/v4_1_finalize_campaign.py",
    "scripts/v4_1_2_verify_runtime_promotion.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for directory in ("src", "contracts", "config"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite frozen Release: {OUTPUT}")
    previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    release = deepcopy(previous)
    release.update({
        "release_id": "v4.1.2-corrective-integration-20261002",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source_tree_sha256": tree_hash(CANDIDATE),
        "supersedes": {
            "path": PREVIOUS.relative_to(ROOT).as_posix(),
            "sha256": sha256(PREVIOUS),
            "note": "v4.1.1 remains immutable; v4.1.2 freezes the strict canonical finalizer without changing taxonomy, datasets, scorers, prompts, construct runtime semantics, source tree, or tested-model roster",
        },
        "execution_integration": {
            "formal_run_suffix": "v4.1-formal",
            "prefrozen_manifest_directory": "data/runs/_v4_1_2_manifests",
            "live_smoke_gate": "artifacts/scientific_closure_v4/live-smoke/V4_1_2_S8_LIVE_SMOKE.json",
            "historical_pilot_gates_consumed": False,
            "frozen_dataset_writes_allowed": False,
            "execution_tool_sha256": {path: sha256(ROOT / path) for path in TOOLS},
        },
        "basis": {
            **previous["basis"],
            "successor_reason": "freeze the strict canonical aggregation, report, dashboard, reproducibility, integrity, and final-delivery consumer; no scientific construct change",
            "provider_calls": 0,
        },
    })
    OUTPUT.write_text(json.dumps(release, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"release_id": release["release_id"], "release_sha256": sha256(OUTPUT),
                      "source_tree_sha256": release["source_tree_sha256"],
                      "supersedes_sha256": release["supersedes"]["sha256"], "provider_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
