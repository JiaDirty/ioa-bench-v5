"""Build a provider-free reproducibility bundle from frozen artifacts."""

from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path


def build_bundle(root: str | Path, run_id: str, output: str | Path) -> Path:
    root, output = Path(root), Path(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    manifest_path = root / "data" / "runs" / run_id / "manifest" / f"{run_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative_paths = [
        "README.md", "AGENTS.md", "pyproject.toml", "src", "config", "worlds", "roles", "scripts", "tests", "contracts", "docs",
        "state/DESIGN_DECISIONS.yaml", "state/PROJECT_STATE.yaml", "state/WORK_QUEUE.yaml",
        "state/WORK_QUEUE_VALIDATION.json", "state/CHANGELOG.md", "data/datasets/DATASET_PACK_v1.yaml", "data/datasets/DATASET_PACK_v2.yaml",
        f"data/runs/{run_id}/manifest", f"data/runs/{run_id}/checkpoint.json", f"data/runs/{run_id}/results.json",
        f"data/runs/{run_id}/completeness.json", f"data/runs/{run_id}/replay", f"data/reports/{run_id}",
        f"artifacts/runs/{run_id}/replay-audit.json", "artifacts/gates/M9.json", "artifacts/gates/M10.json", "artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json",
    ]
    for suite, version in manifest.get("benchmark", {}).get("dataset_versions", {}).items():
        relative_paths.append(f"data/datasets/{suite}/{version}")
    m9_path = root / "artifacts" / "gates" / "M9.json"
    if m9_path.exists():
        m9_gate = json.loads(m9_path.read_text(encoding="utf-8"))
        for suite, evidence in m9_gate.get("evidence", {}).items():
            version = evidence.get("version") if isinstance(evidence, dict) else None
            if version:
                relative_paths.append(f"data/datasets/{suite}/{version}")
    for relative in relative_paths:
        source = root / relative
        if not source.exists():
            continue
        destination = output / relative
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    (output / "environment.json").write_text(json.dumps({
        "profile": manifest.get("profile"),
        "runtime": manifest.get("runtime", {}),
        "tested_model": manifest.get("tested_model", {}),
        "dependency_lock_sha256": manifest.get("runtime", {}).get("dependency_lock_sha256"),
        "provider_credentials_included": False,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {}
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "bundle-manifest.json").write_text(json.dumps({
        "bundle": "ioabench-v1",
        "run_id": run_id,
        "provider_credentials_included": False,
        "manifest_sha256": manifest.get("manifest_sha256"),
        "file_count": len(hashes),
        "content_sha256": hashes,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
