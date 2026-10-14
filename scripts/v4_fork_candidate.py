"""V4-S1: fork the old corrective candidate into a new, non-overwriting directory.

Copies the scientific source tree (src/contracts/config) byte-for-byte and
computes both the per-file hashes and the canonical windows snapshot hash, so
that the pre-revision candidate hash can be independently reproduced.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, windows_snapshot_hash, write_new

OLD = ROOT / "artifacts/scientific_closure_v3_2/corrective-candidate"
NEW = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v2"
SCOPES = ("src", "contracts", "config")


def load_tree(base: Path) -> dict[str, bytes]:
    files = {}
    for scope in SCOPES:
        for p in (base / scope).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                files[p.relative_to(base).as_posix()] = p.read_bytes()
    return files


def main() -> int:
    if NEW.exists():
        raise SystemExit(f"refusing to overwrite {NEW}")
    if not OLD.is_dir():
        raise SystemExit(f"old candidate missing: {OLD}")
    old_files = load_tree(OLD)
    old_tree = windows_snapshot_hash(old_files)

    NEW.mkdir(parents=True)
    for scope in SCOPES:
        src = OLD / scope
        if src.is_dir():
            shutil.copytree(src, NEW / scope,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    new_files = load_tree(NEW)
    new_tree = windows_snapshot_hash(new_files)

    identity = all(old_files[k] == new_files[k] for k in old_files) and set(old_files) == set(new_files)
    report = {
        "artifact": "V4_CANDIDATE_FORK",
        "pass": bool(identity and old_tree == new_tree),
        "provider_calls": 0,
        "old_candidate": {"path": OLD.relative_to(ROOT).as_posix(),
                          "source_tree_sha256": old_tree, "files": len(old_files)},
        "new_candidate": {"path": NEW.relative_to(ROOT).as_posix(),
                          "source_tree_sha256": new_tree, "files": len(new_files)},
        "expected_old_tree_sha256": "7f48188a83a1d5a2e5d0886a9778813076f01c236815795b14c4e110c0becd77",
        "old_tree_matches_expected": old_tree == "7f48188a83a1d5a2e5d0886a9778813076f01c236815795b14c4e110c0becd77",
        "byte_identical_copy": identity,
        "file_hashes": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(new_files.items())},
    }
    write_new(ROOT / "artifacts/scientific_closure_v4/candidate-fork-001.json", report)
    print(json.dumps({"old_tree": old_tree, "new_tree": new_tree, "files": len(new_files),
                      "identical": identity, "matches_expected": report["old_tree_matches_expected"],
                      "new_dir": str(NEW)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
