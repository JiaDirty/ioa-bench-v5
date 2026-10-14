"""Create and verify a versioned workspace handoff without changing old releases.

Usage: python -B scripts/package_workspace_snapshot.py --output exports/<new-dir>
       python -B scripts/package_workspace_snapshot.py --verify <archive.zip>
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
             ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox"}
ARCHIVES = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"}
KEY_TOKEN = re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}")
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
PREFIX = "ioa_codex_spec/"
META = PREFIX + "_snapshot/"


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def local_secrets():
    values = []
    for path in ROOT.glob(".env*"):
        if path.name.endswith((".example", ".sample", ".template")):
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip("\"'")
            if re.search(r"key|secret|token|password", key, re.I) and len(value) >= 12:
                values.append(value.encode("utf-8"))
    return values


def selection():
    included, excluded = [], []
    for base, dirs, names in os.walk(ROOT, followlinks=False):
        base = Path(base)
        for name in dirs[:]:
            path = base / name
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"Unreviewed linked directory: {relative}")
            if name in SKIP_DIRS or relative in {"exports", "archive"}:
                dirs.remove(name)
                excluded.append({"path": relative + "/", "reason": "environment_cache_or_output"})
        for name in names:
            path = base / name
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink():
                raise ValueError(f"Unreviewed linked file: {relative}")
            reason = None
            if name.startswith(".env") and not name.endswith((".example", ".sample", ".template")):
                reason = "local_credentials"
            elif path.suffix.lower() in {".pem", ".p12", ".pfx", ".key"}:
                reason = "credential_container"
            elif path.suffix.lower() in {".pyc", ".pyo"}:
                reason = "regenerable_bytecode"
            elif path.suffix.lower() in ARCHIVES:
                reason = "archive_retained_on_host_not_nested"
            if reason:
                item = {"path": relative, "reason": reason, "bytes": path.stat().st_size}
                if reason == "archive_retained_on_host_not_nested":
                    item["sha256"] = digest_file(path)
                excluded.append(item)
            else:
                included.append(path)
    return sorted(included), sorted(excluded, key=lambda item: item["path"])


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        for name in names:
            if not name.startswith(PREFIX) or ".." in PurePosixPath(name).parts or "\\" in name:
                raise ValueError("Unsafe archive path")
        metadata = {name: json.loads(archive.read(META + name))
                    for name in ("FILES.json", "EXCLUDED.json", "SNAPSHOT.json")}
        inventory = metadata["FILES.json"]
        expected = {PREFIX + row["path"] for row in inventory}
        expected |= {META + name for name in ("FILES.json", "EXCLUDED.json", "SNAPSHOT.json")}
        if set(names) != expected:
            raise ValueError("Archive membership differs from inventory")
        for row in inventory:
            with archive.open(PREFIX + row["path"]) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != row["sha256"] or archive.getinfo(PREFIX + row["path"]).file_size != row["bytes"]:
                raise ValueError(f"Archive content mismatch: {row['path']}")
        return {"file_count": len(inventory), "entry_count": len(names),
                "uncompressed_bytes": sum(row["bytes"] for row in inventory),
                "all_entry_crc_checked_during_read": True, "all_file_sha256_match": True}


def build(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "exports"):
        raise ValueError("Output must be a new directory under workspace exports/")
    output.mkdir(parents=True, exist_ok=False)
    files, excluded = selection()
    secrets = local_secrets()
    archive_path = output / ("IoA-Bench-workspace-" + output.name + ".zip")
    temporary = archive_path.with_suffix(".zip.partial")
    inventory = []
    before_stats = {}
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for index, path in enumerate(files, 1):
            relative = path.relative_to(ROOT).as_posix()
            before = path.stat()
            before_stats[relative] = (before.st_size, before.st_mtime_ns)
            digest = hashlib.sha256()
            tail = b""
            with path.open("rb") as source, archive.open(PREFIX + relative, "w", force_zip64=True) as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    sample = tail + chunk
                    if any(value in sample for value in secrets) or KEY_TOKEN.search(sample) or PRIVATE_KEY.search(sample):
                        raise ValueError(f"Credential pattern in included file (value suppressed): {relative}")
                    digest.update(chunk)
                    target.write(chunk)
                    tail = sample[-4096:]
            after = path.stat()
            if (after.st_size, after.st_mtime_ns) != before_stats[relative]:
                raise ValueError(f"File changed while packaging: {relative}")
            inventory.append({"path": relative, "bytes": before.st_size, "sha256": digest.hexdigest()})
            if index % 2000 == 0:
                print(json.dumps({"phase": "compress", "files": index, "total": len(files)}), flush=True)
        current, _ = selection()
        if current != files:
            raise ValueError("Workspace membership changed during packaging")
        for path in files:
            st = path.stat()
            if (st.st_size, st.st_mtime_ns) != before_stats[path.relative_to(ROOT).as_posix()]:
                raise ValueError("Workspace file changed during packaging")
        snapshot = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "kind": "workspace_handoff_not_formal_acceptance", "provider_calls": 0,
                    "read_first": "docs/HANDOFF_20261001_WORKSPACE.md",
                    "formal_v4_run_results_count": len(list((ROOT / "data/runs").glob("*-v4-formal/results.json"))),
                    "exclusion_note": "Credentials, caches, environments, exports and pre-existing archives excluded; archive index retained.",
                    "secret_scan": "Known local .env secrets, key-token patterns and private-key headers absent from included content.",
                    "known_issues": "See handoff note; no benchmark bug was repaired by this packaging task."}
        for name, value in (("FILES.json", inventory), ("EXCLUDED.json", excluded), ("SNAPSHOT.json", snapshot)):
            archive.writestr(META + name, json_bytes(value))
    print(json.dumps({"phase": "verify_every_entry", "files": len(files)}), flush=True)
    result = verify(temporary)
    temporary.rename(archive_path)
    result.update({"archive": archive_path.name, "bytes": archive_path.stat().st_size,
                   "sha256": digest_file(archive_path), "provider_calls": 0,
                   "secret_scan": "PASS", "code_tests_rerun": False})
    (output / "PACKAGE_VERIFICATION.json").write_bytes(json_bytes(result))
    (output / (archive_path.name + ".sha256")).write_text(result["sha256"] + "  " + archive_path.name + "\n", encoding="ascii")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify), indent=2))
    else:
        build(args.output)
