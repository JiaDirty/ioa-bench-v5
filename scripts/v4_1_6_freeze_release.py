"""Freeze the non-semantic v4.1.6 delivery-integration successor Release."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v7"
PREVIOUS = ROOT / "release/BENCHMARK_RELEASE_v4.1.5-corrective-integration-20261002.json"
OUTPUT = ROOT / "release/BENCHMARK_RELEASE_v4.1.6-corrective-integration-20261002.json"
TOOLS = (
    "scripts/run_online_campaign.py",
    "scripts/v4_1_6_live_smoke.py",
    "scripts/v4_1_6_validate_run.py",
    "scripts/v4_1_6_strict_binding_audit.py",
    "scripts/v4_1_6_finalize_campaign.py",
    "scripts/v4_1_6_verify_runtime_promotion.py",
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
        "release_id": "v4.1.6-corrective-integration-20261002",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "source_tree_sha256": tree_hash(CANDIDATE),
        "supersedes": {
            "path": PREVIOUS.relative_to(ROOT).as_posix(),
            "sha256": sha256(PREVIOUS),
            "note": "v4.1.5 remains immutable; v4.1.6 retains every synthetic-human internal response, aligns runtime-version bindings, and hardens post-run/delivery provenance without changing taxonomy, datasets, scorers, prompts, construct semantics, or tested-model roster",
        },
        "execution_integration": {
            "formal_run_suffix": "v4.1-formal",
            "prefrozen_manifest_directory": "data/runs/_v4_1_6_manifests",
            "live_smoke_gate": "artifacts/scientific_closure_v4/live-smoke/V4_1_6_S8_LIVE_SMOKE.json",
            "historical_pilot_gates_consumed": False,
            "frozen_dataset_writes_allowed": False,
            "execution_tool_sha256": {path: sha256(ROOT / path) for path in TOOLS},
        },
        "model_profile_sha256": sha256(ROOT / "release/MODEL_PROFILE_deepseek-v4.1-flash.json"),
        "provenance_contract": {
            "contracts": "release.contracts maps each suite to its frozen contract hash",
            "scorers": "release.scorer_versions maps each suite to its scorer version",
            "runtimes": "release.runtime_versions maps each suite to the emitted replay runtime_version",
            "prompts": "request snapshots in every Replay are authoritative; source tree and release prompt hashes pin their definitions",
            "tools": "request tool definitions plus Release execution_tool_sha256 pin execution tooling",
        },
        "basis": {
            **previous["basis"],
            "successor_reason": "freeze synthetic-human attempt retention, exact runtime bindings, and delivery provenance hardening; no scientific construct change",
            "provider_calls": 0,
        },
    })
    release["runtime_versions"].update({
        "T311": "T311-construct-1.0.0", "T312": "T312-selection-2.0.0", "T313": "T313-delegation-1.0.0",
        "T321": "T321-protocol-1.0.0", "T322": "T322-protocol-1.0.0",
        "T323": "T323-delegation-1.0.0", "T331": "T331-propagation-1.0.0",
        "T332": "T332-disclosure-1.0.0", "T333": "T333-disclosure-1.0.0",
        "T341": "T341-deliberation-2.0.0", "T342": "T342-propagation-1.0.0",
        "T343": "T343-deliberation-2.0.0", "T351": "T351-incentive-reputation-2.0.0",
        "T352": "T352-incentive-reputation-2.1.0", "T353": "T353-selection-2.2.0",
        "T361": "T361-agency-2.1.1", "T362": "T362-agency-2.1.1", "T363": "T363-agency-2.1.1",
    })
    OUTPUT.write_text(json.dumps(release, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"release_id": release["release_id"], "release_sha256": sha256(OUTPUT),
                      "source_tree_sha256": release["source_tree_sha256"],
                      "supersedes_sha256": release["supersedes"]["sha256"], "provider_calls": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
