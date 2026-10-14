"""Package the IoA-Bench v5 source workspace into a verified zip (maintenance task).

Follows the 20261010 source-review precedent: current source, tests, contracts, configs, docs,
state ledgers, prompt/role/scenario/world assets and selected v5 evidence — excluding secrets
(.env), caches, heavy historical replay data (data/), historical workspace zips, exports and
release blobs. Every included file is recorded with SHA-256 in PACKAGE_VERIFICATION.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAMP = "20261011-r3"
OUT_DIR = ROOT / "exports" / f"workspace-source-{STAMP}"
OUT_ZIP = OUT_DIR / f"IoA-Bench-source-{STAMP}.zip"
MANIFEST = OUT_DIR / "PACKAGE_VERIFICATION.json"

INCLUDE_DIRS = [
    "src", "scripts", "tests", "contracts", "config", "docs", "state", "adr",
    "prompts", "roles", "scenarios", "templates", "worlds",
]
INCLUDE_FILES = [
    "pyproject.toml", "README.md", "AGENTS.md", "CLAUDE.md", ".zcodeignore", ".env.example",
]
SELECTED_EVIDENCE_DIRS = [
    "artifacts/v5/gates",
    "artifacts/v5/dynamic_world",
    "artifacts/v5/probes",
    "artifacts/v5/data_factory",
]
EXCLUDE_DIR_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
                     "ioa_bench.egg-info", "node_modules"}
EXCLUDE_FILE_NAMES = {".env", ".env.local"}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect() -> list[Path]:
    files: list[Path] = []
    for d in INCLUDE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not (set(path.parts) & EXCLUDE_DIR_PARTS):
                files.append(path)
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.exists():
            files.append(path)
    for d in SELECTED_EVIDENCE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not (set(path.parts) & EXCLUDE_DIR_PARTS):
                files.append(path)
    # dedupe while keeping order
    seen = set()
    unique = []
    for path in sorted(files):
        if path.as_posix() not in seen:
            seen.add(path.as_posix())
            unique.append(path)
    return unique


def main() -> int:
    if OUT_ZIP.exists():
        print(f"REFUSED: {OUT_ZIP} already exists", file=sys.stderr)
        return 1
    files = collect()
    entries = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in files:
            arcname = Path("IoA-Bench-v5-workspace") / path.relative_to(ROOT)
            bundle.write(path, arcname.as_posix())
            entries.append({"path": path.relative_to(ROOT).as_posix(),
                            "bytes": path.stat().st_size,
                            "sha256": sha256_of(path)})
    zip_sha = sha256_of(OUT_ZIP)
    verification = {
        "kind": "ioabench.v5.workspace-source-package/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zip": OUT_ZIP.name,
        "zip_bytes": OUT_ZIP.stat().st_size,
        "zip_sha256": zip_sha,
        "file_count": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries),
        "excludes": [".env (secret)", "caches", "data/ (historical replay datasets, 3.9 GB)",
                     "artifacts except selected v5 evidence", "historical workspace zips",
                     "exports/", "release/ blobs", "claude_export/"],
        "includes": INCLUDE_DIRS + INCLUDE_FILES + SELECTED_EVIDENCE_DIRS,
        "files": entries,
    }
    MANIFEST.write_text(json.dumps(verification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK files={len(entries)} zip={OUT_ZIP.name} zip_sha256={zip_sha[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
