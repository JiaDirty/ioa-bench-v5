"""Codex snapshot acceptance harness (P3 preparation, post-audit DW-AUDIT-007).

Given a Codex-delivered snapshot directory plus its SHA-256 manifest, this tool performs the
read-only acceptance review WITHOUT writing to the Codex directory:

  1. hash verification: every manifest entry is re-hashed and compared;
  2. mainline diff: each snapshot file is classified vs the mainline tree
     (identical / modified / new — by SHA-256 against the same relative path);
  3. portability classification: which files map to mainline integration targets
     (ai_generation contract, adapters, tests) vs Codex-local artifacts;
  4. report: a machine-readable acceptance report listing per-file verdicts, the files a
     selective integration would touch, and any FAIL entries that block acceptance.

The snapshot itself is never modified. Integration remains a separate, reviewed step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTABILITY_PREFIXES = ("src/ioabench/v5/ai_generation/", "scripts/v5/", "tests/v5/")
CODE_SUFFIXES = (".py", ".json")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(snapshot_dir: Path) -> dict[str, str]:
    for name in ("MANIFEST.json", "manifest.json", "SNAPSHOT_HASHES.json"):
        candidate = snapshot_dir / name
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            # accept {"files": {path: sha}} or {"files": [{path, sha256}]} or a flat {path: sha}
            files = data.get("files", data)
            if isinstance(files, dict):
                return {str(k): str(v) for k, v in files.items()}
            if isinstance(files, list):
                return {str(e["path"]): str(e.get("sha256", e.get("sha")))
                        for e in files if "path" in e}
    raise SystemExit(f"no SHA-256 manifest found in {snapshot_dir} "
                     f"(expected MANIFEST.json / manifest.json / SNAPSHOT_HASHES.json)")


def classify_vs_mainline(snapshot_dir: Path, rel_path: str) -> str:
    mainline = ROOT / rel_path
    if not mainline.exists():
        return "new"
    return "identical" if sha256_of(mainline) == sha256_of(snapshot_dir / rel_path) else "modified"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", required=True,
                        help="immutable Codex snapshot directory (read-only)")
    parser.add_argument("--out", required=True, help="acceptance report path (must not exist)")
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot_dir)
    if not snapshot_dir.is_dir():
        print(f"ERROR: snapshot dir {snapshot_dir} not found", file=sys.stderr)
        return 1
    out_path = Path(args.out)
    if out_path.exists():
        print(f"REFUSED: {out_path} exists", file=sys.stderr)
        return 1

    manifest = load_manifest(snapshot_dir)
    hash_failures = []
    classifications = []
    for rel_path, expected in sorted(manifest.items()):
        actual_file = snapshot_dir / rel_path
        if not actual_file.is_file():
            hash_failures.append({"path": rel_path, "problem": "missing in snapshot"})
            continue
        actual = sha256_of(actual_file)
        if actual != expected:
            hash_failures.append({"path": rel_path, "problem": "sha256 mismatch",
                                  "expected": expected, "actual": actual})
            continue
        verdict = classify_vs_mainline(snapshot_dir, rel_path)
        portable = rel_path.startswith(PORTABILITY_PREFIXES) and rel_path.endswith(CODE_SUFFIXES)
        classifications.append({"path": rel_path, "vs_mainline": verdict,
                                "portable_integration_candidate": portable,
                                "sha256": actual})

    integration_candidates = [c for c in classifications
                              if c["portable_integration_candidate"]
                              and c["vs_mainline"] in ("new", "modified")]
    report = {
        "kind": "ioabench.v5.codex-snapshot-acceptance/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot_dir": str(snapshot_dir),
        "manifest_entries": len(manifest),
        "hash_verified": not hash_failures,
        "hash_failures": hash_failures,
        "files": classifications,
        "integration_candidates": [c["path"] for c in integration_candidates],
        "summary": {
            "identical_to_mainline": sum(1 for c in classifications if c["vs_mainline"] == "identical"),
            "modified_vs_mainline": sum(1 for c in classifications if c["vs_mainline"] == "modified"),
            "new_vs_mainline": sum(1 for c in classifications if c["vs_mainline"] == "new"),
        },
        "acceptance": ("PASS" if not hash_failures else "FAIL: hash verification failed — "
                                                     "snapshot is not immutable-verifiable; request a corrected manifest"),
        "note": ("read-only acceptance review; selective integration is a separate reviewed step "
                 "and never writes to the Codex directory"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK entries={len(manifest)} hash_verified={report['hash_verified']} "
          f"integration_candidates={len(integration_candidates)} -> {out_path}")
    return 0 if not hash_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
