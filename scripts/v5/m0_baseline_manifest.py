"""Create the M0 read-only baseline hash manifest for the dynamic-world phase.

Scope: v5-relevant source/scripts/tests/contracts/docs/state files only. This is an evidence
anchor for later compatibility diffs (M2 must keep the 18 existing suites regression-clean);
it is NOT a backup copy of historical evidence. Refuses to overwrite an existing manifest.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    "src/ioabench/v5",
    "scripts/v5",
    "tests/v5",
    "contracts/v5",
    "docs/v5",
    "state/WORK_QUEUE_V5_DYNAMIC_WORLD.yaml",
    "state/PROJECT_STATE.yaml",
    "AGENTS.md",
]
EXCLUDE = ("__pycache__", ".pytest_cache")
DEST = ROOT / "artifacts/v5/dynamic_world/m0-baseline-manifest.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if DEST.exists():
        print(f"REFUSED: {DEST} already exists", file=sys.stderr)
        return 1
    entries: list[dict[str, object]] = []
    for target in TARGETS:
        full = ROOT / target
        if full.is_dir():
            for path in sorted(full.rglob("*")):
                if not path.is_file() or any(part in EXCLUDE for part in path.parts):
                    continue
                entries.append({
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_of(path),
                })
        elif full.is_file():
            entries.append({
                "path": Path(target).as_posix(),
                "bytes": full.stat().st_size,
                "sha256": sha256_of(full),
            })
        else:
            print(f"WARN: missing target {target}", file=sys.stderr)
    entries.sort(key=lambda e: str(e["path"]))
    manifest = {
        "kind": "ioabench.v5.dynamic-world.m0-baseline/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": ("read-only baseline hash manifest of v5-relevant files at dynamic-world M0; "
                    "evidence anchor for later compatibility diffs; NOT a copy of historical evidence"),
        "file_count": len(entries),
        "total_bytes": sum(int(e["bytes"]) for e in entries),
        "files": entries,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK files={len(entries)} bytes={manifest['total_bytes']} -> {DEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
