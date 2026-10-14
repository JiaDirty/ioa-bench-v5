"""Replay recorded source groups in fresh processes, without provider access."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/scientific_closure_v3_2"


def snapshot_hash(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for directory in ("src", "contracts", "config"):
        for name in sorted((n for n in files if n.startswith(directory + "/")), key=PureWindowsPath):
            digest.update(name.encode("utf-8"))
            digest.update(hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


def recovered_files(recovery: dict, source_hash: str) -> dict[str, bytes]:
    history = recovery.get("artifact") == "LITERAL_HISTORY_SOURCE_RECOVERY"
    recipe = recovery["recovered"].get(source_hash) if history else recovery["reconstructions"].get(source_hash)
    archive_ref = recipe["base_archive"] if recipe else next(a for a in recovery["archives"] if a["source_sha256"] == source_hash)
    archive_path = ROOT / (archive_ref["path"] if isinstance(archive_ref, dict) else archive_ref)
    if isinstance(archive_ref, dict):
        with archive_path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == archive_ref["sha256"]
    with ZipFile(archive_path) as archive:
        files = {n: archive.read(n) for n in archive.namelist() if n.startswith(("src/", "contracts/", "config/")) and not n.endswith("/") and "__pycache__" not in n.split("/")}
    if history:
        files = {n: data for n, data in files.items() if n in recipe["file_hashes"]}
        for name, ref in recipe["overrides"].items():
            data = (ROOT / ref["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == ref["sha256"]
            files[name] = data
    elif recipe:
        for name in recipe["current_byte_paths"]:
            if (ROOT / name).is_file(): files[name] = (ROOT / name).read_bytes()
            else: files.pop(name, None)
    if recipe:
        assert {n: hashlib.sha256(v).hexdigest() for n, v in files.items()} == recipe["file_hashes"]
    assert snapshot_hash(files) == source_hash, "reconstructed source does not match recorded hash"
    return files


def child(runtime_root: Path, source_hash: str, output: Path) -> int:
    files = {p.relative_to(runtime_root).as_posix(): p.read_bytes() for directory in ("src", "contracts", "config")
             for p in (runtime_root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert snapshot_hash(files) == source_hash  # Validate before importing reconstructed code.
    sys.path.insert(0, str(runtime_root / "src"))
    import ioabench
    # The audit's authoritative dataset roster is metadata absent in older code.
    name = "ioabench.frozen_versions"
    spec = importlib.util.spec_from_file_location(name, ROOT / "src/ioabench/frozen_versions.py")
    roster = importlib.util.module_from_spec(spec)
    sys.modules[name] = roster
    spec.loader.exec_module(roster)
    spec = importlib.util.spec_from_file_location("closure_audit", ROOT / "scripts/scientific_closure.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert Path(ioabench.__file__).resolve().is_relative_to(runtime_root.resolve())
    assert audit.source_tree_hash(runtime_root) == source_hash
    inventory = audit.read_json(ROOT / "artifacts/gates/V32_S0_EVIDENCE_INVENTORY.json")
    suites = [row["suite"] for row in inventory["suites"] if source_hash in row["case_source_hashes"]]
    expected_cases = sum(row["case_source_hashes"].get(source_hash, 0) for row in inventory["suites"])
    reports = [audit.trace_replay(suite, 0, False, suite == "T353", source_hash) for suite in suites]
    origins = {name: str(Path(module.__file__).resolve().relative_to(runtime_root.resolve()))
               for name, module in sys.modules.items() if name.startswith("ioabench") and name != "ioabench.frozen_versions" and getattr(module, "__file__", None)}
    cases_checked = sum(len(s["units"]) for r in reports for s in r["suites"])
    result = {"artifact": "RECOVERED_SOURCE_RECORDED_RESPONSE_REPLAY", "pass": expected_cases > 0 and cases_checked == expected_cases and all(r["pass"] for r in reports),
              "provider_calls": 0, "canonical_acceptance": False, "recorded_source_sha256": source_hash,
              "loaded_module_origins": origins, "reports": reports,
              "cases_checked": cases_checked, "expected_cases": expected_cases,
              "limits": ["T353 verifies primary trajectories only; paired replies are absent.", "No claim about unrecorded attempts or provider counterfactual behavior."]}
    audit.write_new(output, result)
    print(json.dumps({"source": source_hash, "pass": result["pass"], "cases_checked": result["cases_checked"]}), flush=True)
    return 0 if result["pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--source-hash")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history-recovery", type=Path)
    args = parser.parse_args()
    if args.runtime_root:
        return child(args.runtime_root, args.source_hash, args.output)
    if args.output.exists():
        raise FileExistsError(args.output)
    recovery_path = args.history_recovery or BASE / "source-byte-recovery-001.json"
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    hashes = sorted(recovery["recovered"]) if args.history_recovery else sorted({g["recorded_source_sha256"] for row in recovery["suites"] for g in row["groups"] if g["source_bytes_resolved"]})
    if args.source_hash:
        if args.source_hash not in hashes:
            raise ValueError("source hash is not backed by recovered bytes")
        hashes = [args.source_hash]
    reports = []
    with tempfile.TemporaryDirectory(prefix="source-replay-", dir=BASE) as temporary:
        directory = Path(temporary).resolve()
        assert directory.is_relative_to(BASE.resolve())
        for source_hash in hashes:
            runtime_root = directory / source_hash
            files = recovered_files(recovery, source_hash)
            for name, data in files.items():
                assert ":" not in name and ".." not in name.replace("\\", "/").split("/")
                target = (runtime_root / name).resolve()
                assert target.is_relative_to(runtime_root.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            output = args.output.with_name(args.output.stem + "-" + source_hash[:12] + ".json")
            run = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--runtime-root", str(runtime_root), "--source-hash", source_hash, "--output", str(output)], cwd=ROOT, check=False, timeout=300)
            report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"pass": False, "cases_checked": 0}
            reports.append({"path": str(output), "exit_code": run.returncode, "pass": run.returncode == 0 and report["pass"], "cases_checked": report["cases_checked"]})
    result = {"artifact": "RECOVERED_SOURCE_REPLAY_SUMMARY", "pass": bool(reports) and all(r["pass"] for r in reports), "provider_calls": 0, "canonical_acceptance": False, "recovery_manifest": {"path": str(recovery_path), "sha256": hashlib.sha256(recovery_path.read_bytes()).hexdigest()}, "reports": reports, "cases_checked": sum(r["cases_checked"] for r in reports)}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result), flush=True)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
