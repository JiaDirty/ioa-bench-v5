from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "artifacts" / "handoff"
INVENTORY = HANDOFF / "CURRENT_PROJECT_INVENTORY.json"
MANIFEST = HANDOFF / "HANDOFF_BUNDLE_MANIFEST.json"
ZIP_PATH = ROOT / "archive/deliveries/IoA-Bench-v3-20260930-final-delivery.zip"
HANDOFF_DOC = ROOT / "docs" / "PROJECT_HANDOFF_CURRENT_STATE.md"
INDEX = ROOT / "docs" / "EXTERNAL_REVIEW_FILE_INDEX.md"

EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv", "node_modules"}
EXCLUDE_NAMES = {".env", ".env.local", ".env.production", MANIFEST.name}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".tmp", ".bak"}
SECRET_PATTERNS = [
    re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)AIHUBMIX_API_KEY\s*=\s*(?![<\"'])(?!\$\{)[^\s#]+"),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def included(path: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return False
    if path.name in EXCLUDE_NAMES or path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.suffix.lower() == ".zip":
        return False
    if not path.is_file():
        return False
    return True


def files_for_bundle() -> list[Path]:
    return sorted((p for p in ROOT.rglob("*") if included(p)), key=rel)


def tree_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(rel(path).encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
        digest.update(b"\n")
    return digest.hexdigest()


def source_hash() -> str:
    roots = ("src", "contracts", "config", "worlds", "roles", "scripts", "tests")
    paths = [p for root in roots for p in (ROOT / root).rglob("*") if included(p)]
    return tree_hash(sorted(paths, key=rel))


def contract_summary() -> list[dict[str, object]]:
    result = []
    for path in sorted((ROOT / "contracts" / "constructs").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result.append({
            "suite_id": data["suite_id"],
            "construct_name": data["construct_name"],
            "version": data["construct_version"],
            "implementation_status": data["implementation_status"],
            "simulation_only": data["suite_id"] in {"T361", "T362", "T363"},
            "path": rel(path),
            "sha256": sha256_file(path),
        })
    return result


def directory_counts() -> dict[str, dict[str, int]]:
    names = ["src", "contracts", "config", "worlds", "roles", "scripts", "tests", "state", "docs", "data/datasets", "data/runs", "data/reports", "artifacts", "release"]
    result = {}
    for name in names:
        base = ROOT / name
        paths = [p for p in base.rglob("*") if included(p)] if base.exists() else []
        result[name] = {"files": len(paths), "bytes": sum(p.stat().st_size for p in paths)}
    return result


def important_hashes() -> dict[str, str]:
    names = [
        "AGENTS.md", "README.md", "state/PROJECT_STATE.yaml", "state/WORK_QUEUE.yaml",
        "state/WORK_QUEUE_VALIDATION.json", "state/CHANGELOG.md", "state/V2_CHECKPOINT.md",
        "docs/PROJECT_HANDOFF_CURRENT_STATE.md", "docs/EXTERNAL_REVIEW_FILE_INDEX.md",
        "docs/CONSTRUCT_IMPLEMENTATION_GAP_AUDIT_R5.md", "docs/FINAL_SCIENTIFIC_ACCEPTANCE_AUDIT.md",
        "contracts/schema/construct.schema.json", "contracts/schema/run_manifest.schema.json",
        "release/BENCHMARK_RELEASE_v3-20260930.json", "release/MODEL_PROFILE_deepseek-v4.1-flash.json",
        "data/datasets/DATASET_PACK_v4.yaml", "config/synthetic_human.json", "config/scheduler_profile.json",
        "artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json", "artifacts/gates/PHASE_C_CAMPAIGN.json",
        "artifacts/gates/REPLAY_AUDIT_V3.json", "artifacts/gates/INDEPENDENT_SEMANTIC_VALIDATION.json",
        "artifacts/gates/RUN_CLASSIFICATION.json", "artifacts/gates/ONLINE_CAMPAIGN_STATE.json",
        "artifacts/gates/STATE_RECONCILIATION.json", "artifacts/gates/CONCURRENCY_CALIBRATION.json",
        "artifacts/gates/AUX_MODEL_PROFILES.json", "src/ioabench/frozen_versions.py",
        "src/ioabench/runtime/human_agency_simulation.py", "src/ioabench/runtime/synthetic_human.py",
        "scripts/run_online_campaign.py", "scripts/run_online_pilot.py", "scripts/phase_c_campaign.py",
        "tests/construct/test_synthetic_human_model.py", "tests/construct/test_executor_signatures.py",
    ]
    return {name: sha256_file(ROOT / name) for name in names if (ROOT / name).is_file()}


def secret_scan(paths: list[Path]) -> list[str]:
    hits = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(rel(path))
    return hits


def write_index() -> None:
    text = """# IoA-Bench External Review File Index

This index is a navigation aid for the current read-only handoff snapshot. Source code and reproducible artifacts take precedence over historical PASS wording.

## Read first
- `AGENTS.md`: normative research boundaries and v1 rules.
- `docs/PROJECT_HANDOFF_CURRENT_STATE.md`: current state, history, architecture, limitations, and next-stage strategy.
- `artifacts/handoff/CURRENT_PROJECT_INVENTORY.json`: machine-readable snapshot inventory.
- `state/PROJECT_STATE.yaml`, `state/WORK_QUEUE.yaml`, `state/WORK_QUEUE_VALIDATION.json`: governance state; historical `done` does not imply current construct validity.

## Architecture and runtime
- `docs/01_SYSTEM_ARCHITECTURE.md`, `docs/02_DATA_AND_EVENT_MODEL.md`, `docs/16_REFERENCE_IOA_WORLDS_AND_SANDBOX.md`: Reference IoA design.
- `src/ioabench/ioa/`, `src/ioabench/protocols/`, `src/ioabench/sandbox/`: reusable infrastructure.
- `src/ioabench/runtime/offline_run.py`, `src/ioabench/suites/_vertical.py`: legacy generic runtime retained for historical runs.
- `src/ioabench/runtime/construct_runtime.py` and the suite archetype modules: current construct runtime base and suite-specific implementations for all 18 suites.
- `src/ioabench/suites/`: suite generators, scenarios and scorers; current offline acceptance is recorded in the Phase A V2 gate.

## Research decisions and audit
- `docs/04_EVALUATION_18_TESTS.md`, `docs/10_TEST_DATA_RECIPES_18_SUITES.md`: canonical suite definitions and data recipes.
- `docs/18_DESIGN_DECISIONS_REGISTER.md`: research decisions.
- `docs/CONSTRUCT_IMPLEMENTATION_GAP_AUDIT_R5.md`: external r5 construct audit; all 18 historical suites were judged formally present but construct-invalid.
- `docs/FINAL_SCIENTIFIC_ACCEPTANCE_AUDIT.md`: historical r5 remediation report; not the current scientific acceptance decision.
- `docs/T311_CONSTRUCT_VERTICAL_SLICE_ACCEPTANCE.md`, `docs/ADR_CONSTRUCT_REMEDIATION_T311.md`: T311 remediation design.

## Contracts and data
- `contracts/schema/construct.schema.json`: schema for all construct contracts.
- `contracts/constructs/T311.json` through `T363.json`: 18 versioned, schema-valid contracts. Their `implementation_status` fields are repository governance metadata; scientific status must be read with the runtime, baseline, counterfactual and replay evidence below.
- `src/ioabench/data_generation/`, `docs/09_DATA_GENERATION_AND_DATASET_LIFECYCLE.md`: generation and freeze framework.
- `data/datasets/DATASET_PACK_v4.yaml`: the frozen authoritative Benchmark Dataset Pack (18 suites); v1/v2 remain as historical provenance.

## T311 evidence
- `src/ioabench/suites/t311/construct_scoring.py`: causal scorer using actions, delegation, state and hidden Oracle join.
- `src/ioabench/replay/construct_audit.py`: replay integrity checks.
- `tests/construct/test_t311_construct.py`: 24 offline construct tests.
- `data/datasets/T311-dev-mini/`: development fixture data; not a formal new dataset.

## Historical runs and artifacts
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/`: historical 1620-case r5 run; preserve for audit, do not interpret as final construct-valid evidence.
- `data/runs/` and `artifacts/runs/`: all retained historical runs, mock runs and replay artifacts.
- `artifacts/gates/`, `artifacts/audits/`, `data/reports/`: historical gates, audits and reports.
- `release/BENCHMARK_RELEASE_v3-20260930.json` + `release/MODEL_PROFILE_deepseek-v4.1-flash.json`: the frozen Benchmark Release and tested-model profile.

## Tests and reproducibility
- `tests/`: offline unit, contract, construct, replay, scorer, baseline, and historical gate tests.
- `scripts/validate_spec.py` or `python -m ioabench.cli validate-spec`: offline schema/spec validation.
- `artifacts/handoff/HANDOFF_BUNDLE_MANIFEST.json`: external companion manifest for the ZIP hash, CRC, exclusions and secret scan.

## Known boundary
This snapshot does not call AIHubMix, generate datasets, or modify historical runs, gates or frozen datasets. It packages the completed benchmark: frozen Benchmark Release v3-20260930, the completed deepseek-v4.1-flash campaign (18x90/90 terminal, `artifacts/gates/ONLINE_CAMPAIGN_STATE.json`), G2 independent validation (`artifacts/gates/INDEPENDENT_SEMANTIC_VALIDATION.json`), replay audit (`artifacts/gates/REPLAY_AUDIT_V3.json`), Phase C results and dashboard (`artifacts/gates/PHASE_C_CAMPAIGN.json`, `artifacts/reports/`), and the final scientific acceptance (`artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`, verdict PASS).
"""
    INDEX.write_text(text, encoding="utf-8")


def project_state_scalar(name: str, default: str = "") -> str:
    prefix = f"{name}:"
    for line in (ROOT / "state" / "PROJECT_STATE.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip().strip('"\'')
    return default


def build() -> None:
    HANDOFF.mkdir(parents=True, exist_ok=True)
    write_index()
    now = datetime.now(timezone.utc).isoformat()
    bundle_files = files_for_bundle()
    contracts = contract_summary()
    inventory = {
        "snapshot_timestamp_utc": now,
        "workspace": str(ROOT),
        "snapshot_type": "current_external_review_handoff_readonly",
        "source_tree_hash": {"algorithm": "sha256(path\\0file_sha256\\n)", "value": source_hash(), "roots": ["src", "contracts", "config", "worlds", "roles", "scripts", "tests"]},
        "python": sys.version,
        "platform": platform.platform(),
        "dependency_lock": {"path": "config/dependencies.lock.json", "sha256": sha256_file(ROOT / "config/dependencies.lock.json")},
        "important_file_sha256": important_hashes(),
        "construct_contracts": contracts,
        "datasets": sorted(p.name for p in (ROOT / "data" / "datasets").glob("*") if p.is_file() or p.is_dir()),
        "historical_runs": sorted(p.name for p in (ROOT / "data" / "runs").iterdir() if p.is_dir()),
        "current_state": {"project_state": "state/PROJECT_STATE.yaml", "work_queue": "state/WORK_QUEUE.yaml", "status": project_state_scalar("status"), "current_milestone": project_state_scalar("current_milestone"), "final_acceptance": "artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json (verdict PASS)", "benchmark_release": "release/BENCHMARK_RELEASE_v3-20260930.json", "online_campaign_state": "artifacts/gates/ONLINE_CAMPAIGN_STATE.json", "phase_c": "artifacts/gates/PHASE_C_CAMPAIGN.json (verdict complete)", "phase_c_dashboard": "artifacts/reports/phase_c_dashboard.html", "phase_c_report": "artifacts/reports/phase_c_report.md"},
        "test_summary": {"source": "full isolated regression after the final source state: 812 passed, 2 skipped (key-gated integration tests); no test rerun during packaging", "linux_ci": "NOT VERIFIED (Windows runtime profile is the frozen target)"},
        "active_runtime_modules": ["src/ioabench/runtime/t311_construct.py", "src/ioabench/runtime/t311_fixture.py", "src/ioabench/runtime/t311_baselines.py", "src/ioabench/runtime/discovery_selection.py", "src/ioabench/runtime/delegation_provenance.py", "src/ioabench/runtime/protocol_state_machine.py", "src/ioabench/runtime/network_propagation.py", "src/ioabench/runtime/disclosure_inference.py", "src/ioabench/runtime/deliberation_norm.py", "src/ioabench/runtime/incentive_reputation.py", "src/ioabench/runtime/human_agency_simulation.py", "src/ioabench/suites/t311/construct_scoring.py", "src/ioabench/replay/construct_audit.py"],
        "legacy_runtime_modules": ["src/ioabench/runtime/offline_run.py", "src/ioabench/suites/_vertical.py"],
        "known_limitations": ["single-execution per case per tested model: results do not estimate within-case run variance", "T361-T363 are SIMULATION_ONLY model-based synthetic-human results; no claims about real human agency", "INVALID_MODEL_OUTPUT (13 cases) is a recorded terminal outcome, never scored safe", "Linux/CI not verified; Windows local runtime is the frozen profile", "tested model roster is deepseek-v4.1-flash only per user decision (2026-09-30)"],
        "counts": {"workspace_bundle_files": len(bundle_files), "workspace_bundle_bytes": sum(p.stat().st_size for p in bundle_files), "contracts": len(contracts), "source_directories": directory_counts()},
        "secret_policy": "API keys, .env files, private keys and old ZIP bundles are excluded; no secret value is stored in this inventory.",
    }
    INVENTORY.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bundle_files = files_for_bundle()
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in bundle_files:
            archive.write(path, rel(path))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        crc = "PASS" if bad is None else f"FAIL:{bad}"
        entries = len(archive.infolist())
    included_hits = secret_scan(bundle_files)
    manifest = {
        "snapshot_timestamp_utc": now,
        "zip_filename": ZIP_PATH.name,
        "zip_path": rel(ZIP_PATH),
        "zip_size_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256_file(ZIP_PATH),
        "entry_count": entries,
        "crc_validation": crc,
        "secret_scan": {"status": "PASS" if not included_hits else "FAIL", "matched_included_files": included_hits, "checked_patterns": ["API key material", "private key headers", "non-empty AIHUBMIX_API_KEY assignment"]},
        "source_tree_hash": inventory["source_tree_hash"],
        "inventory_path": rel(INVENTORY),
        "inventory_sha256": sha256_file(INVENTORY),
        "handoff_document_path": rel(HANDOFF_DOC),
        "handoff_document_sha256": sha256_file(HANDOFF_DOC),
        "file_index_path": rel(INDEX),
        "excluded_patterns": sorted(EXCLUDE_DIRS | EXCLUDE_NAMES | EXCLUDE_SUFFIXES | {"*.zip"}),
        "critical_files": ["AGENTS.md", "docs/PROJECT_HANDOFF_CURRENT_STATE.md", "docs/EXTERNAL_REVIEW_FILE_INDEX.md", "artifacts/handoff/CURRENT_PROJECT_INVENTORY.json", "state/PROJECT_STATE.yaml", "state/WORK_QUEUE.yaml", "contracts/schema/construct.schema.json", "contracts/constructs/T311.json", "src/ioabench/runtime/t311_construct.py", "tests/construct/test_t311_construct.py"],
        "bundle_manifest_included": False,
        "bundle_manifest_note": "This companion manifest is written after ZIP creation so the ZIP hash is non-circular; the inventory and handoff documents are included in the ZIP.",
        "scope": "current workspace handoff; packaging does not call providers, generate datasets, or modify historical runs/gates",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"zip": rel(ZIP_PATH), "size": manifest["zip_size_bytes"], "sha256": manifest["zip_sha256"], "entries": entries, "crc": crc, "secret_scan": manifest["secret_scan"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    build()
