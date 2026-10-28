"""Versioned, secret-scanned development handoff with explicit source/evidence bindings."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import package_workspace_snapshot as pack
from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.evaluation import writer_lock

BASELINE = "e6e3ecff0ce3661251b8efb2cea20ca73301f185"
DEFAULT_OUT = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020"
DEFAULT_OUTPUT = ROOT / "exports/development-factory-handoff-20261020"
DEFAULT_NAME = "IoA-Bench-v5-Development-Factory-HANDOFF-20261020.zip"
CODE_FOLDERS = {"src", "contracts", "config", "scripts", "tests", "docs", "state"}
ROOT_FILES = {"AGENTS.md", "README.md", "pyproject.toml", "uv.lock", "requirements.txt", ".gitignore"}
EXCLUDED = ["credentials and credential containers", ".git database", "caches and locks",
            "unrelated untracked user files", "unbound historical archives"]
OTHER_KEY = re.compile(rb"\b(?:AIza[A-Za-z0-9_-]{30,}|AKIA[0-9A-Z]{16})\b")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def safe_path(relative):
    parts = PurePosixPath(relative)
    if not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative or ":" in relative:
        raise ValueError("unsafe handoff member path")
    return parts


def selected_file(path):
    relative = path.relative_to(ROOT)
    if (any(part in pack.SKIP_DIRS for part in relative.parts) or path.suffix.lower() in {".pyc", ".pyo"}
            or path.name.endswith(".lock") and path.name != "uv.lock"):
        return False
    if path.name.startswith(".env") or path.suffix.lower() in {".pem", ".p12", ".pfx", ".key"}:
        return False
    if path.is_symlink() or any(parent.is_junction() for parent in [path, *path.parents] if parent != ROOT.parent):
        raise ValueError("linked source cannot be packaged")
    return True


def known_secrets():
    values = set(pack.local_secrets())
    values.update(value.encode("utf-8") for key, value in os.environ.items()
                  if re.search(r"api.?key|secret|token|password", key, re.I) and len(value) >= 12)
    return values


def scan_blob(data, name, secrets, *, depth=0):
    if (any(value in data for value in secrets) or pack.KEY_TOKEN.search(data)
            or pack.PRIVATE_KEY.search(data) or OTHER_KEY.search(data)):
        raise ValueError("credential scan failed; value suppressed: " + name)
    if name.lower().endswith(".zip"):
        if depth >= 3:
            raise ValueError("nested archive depth exceeds verified scope")
        with zipfile.ZipFile(BytesIO(data)) as archive:
            for member in archive.infolist():
                safe_path(member.filename.rstrip("/"))
                if Path(member.filename).name.startswith(".env"):
                    raise ValueError("credential filename in nested archive")
                if not member.is_dir():
                    scan_blob(archive.read(member), name + "!" + member.filename, secrets, depth=depth + 1)


def workspace_relative(value, original_root=None):
    root = str(original_root or ROOT)
    cls = PureWindowsPath if re.match(r"^[A-Za-z]:", str(value)) else PurePosixPath
    path = cls(str(value))
    if path.is_absolute():
        path = path.relative_to(cls(root))
    relative = path.as_posix()
    safe_path(relative)
    return relative


def generation_evidence(source, root=None):
    """Trace only a candidate's declared reuse chain and actual paid-source receipts."""
    root = Path(root or ROOT).resolve()
    def bounded(value):
        path = Path(value)
        path = (path if path.is_absolute() else root / path).resolve()
        if not path.is_relative_to(root):
            raise ValueError("generation reuse source escapes workspace")
        # Native Path handles relative Windows backslashes before archive syntax validation.
        return root / workspace_relative(path, root)
    current, chain, files, seen = bounded(source), [], {}, set()
    def retain(path):
        if not path.is_file():
            raise ValueError("generation evidence file missing: " + workspace_relative(path, root))
        files[workspace_relative(path, root)] = pack.digest_file(path)
    while True:
        if current in seen:
            raise ValueError("generation reuse cycle detected")
        if not current.is_dir():
            raise ValueError("generation reuse source directory missing")
        seen.add(current)
        chain.append(workspace_relative(current, root))
        for name in ("RESULT.json", "TERMINAL.json", "MANIFEST.json", "GENERATION_STAGES.json"):
            if (current / name).is_file():
                retain(current / name)
        reuse_path = current / "GENERATION_REUSE.json"
        if not reuse_path.exists():
            break
        retain(reuse_path)
        reuse = read(reuse_path)
        if not reuse.get("source_candidate"):
            raise ValueError("generation reuse has no source candidate")
        target = bounded(reuse["source_candidate"])
        for filename, field in (("RESULT.json", "source_result_sha256"), ("MANIFEST.json", "source_manifest_sha256"),
                                ("GENERATION_STAGES.json", "source_stages_sha256")):
            if reuse.get(field) is not None:
                path = target / filename
                if not path.is_file() or pack.digest_file(path) != reuse[field]:
                    raise ValueError("generation reuse source binding changed: " + filename)
        current = target
    previous, missing = current.parent.parent, []
    for filename in ("REQUEST_LEDGER.jsonl", "MODEL_CATALOG.json"):
        path = previous / filename
        if path.is_file():
            retain(path)
        else:
            missing.append(workspace_relative(path, root))
    ledger = previous / "REQUEST_LEDGER.jsonl"
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8-sig").splitlines():
            row = json.loads(line)
            if not row.get("receipt_path"):
                continue
            receipt = (previous / row["receipt_path"]).resolve()
            if not receipt.is_relative_to(previous) or not receipt.is_relative_to(root):
                raise ValueError("generation accounting receipt escapes run root")
            retain(receipt)
            if files[workspace_relative(receipt, root)] != row.get("receipt_sha256"):
                raise ValueError("generation accounting receipt binding changed")
    return {"chain_directories": chain, "paid_source_directory": workspace_relative(current, root),
            "files": files, "missing": missing}


def selection(out):
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    files = {ROOT / name for name in tracked if name and (PurePosixPath(name).parts[0] in CODE_FOLDERS or name in ROOT_FILES)}
    # Match the authoritative hash inputs, including ignored installation metadata.
    runtime_files = {path for directory in ("src", "contracts", "config") for path in (ROOT / directory).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts}
    files.update(runtime_files)
    files.update(path for path in out.rglob("*") if path.is_file())
    census = read(out / "BASELINE_CENSUS.json")
    candidates, revisions, history_indexes = set(), set(), set()
    for row in census["pairs"]:
        directory = ROOT / workspace_relative(row["source_directory"])
        candidates.add(directory)
        previous = directory.parent.parent
        revisions.add(previous / "source_revisions" / row["source_runtime_sha256"])
        history_indexes.update((previous / "history").glob("*.json"))
    candidates.update(path.parent for path in (out / "candidates").glob("*/RESULT.json"))
    for path in out.rglob("AUDIT_PACKET.json"):
        candidates.add(ROOT / workspace_relative(read(path)["source_binding"]["directory"]))
    generation_bindings = {}
    for directory in sorted(candidates):
        binding = generation_evidence(directory)
        generation_bindings[workspace_relative(directory)] = binding
        candidates.update(ROOT / name for name in binding["chain_directories"])
        files.update(ROOT / name for name in binding["files"])
    history_indexes.update((out / "history").rglob("*.json"))
    prior = ROOT / "artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z/HISTORY_INDEX_V3.json"
    history_indexes.add(prior)
    for directory in [*candidates, *revisions]:
        if not directory.is_dir():
            raise ValueError("bound candidate/runtime directory missing: " + workspace_relative(directory))
        files.update(path for path in directory.rglob("*") if path.is_file())
    for index in history_indexes:
        files.add(index)
        for name, digest in read(index)["source_sha256"].items():
            path = (ROOT / name).resolve()
            if not path.is_relative_to(ROOT) or pack.digest_file(path) != digest:
                raise ValueError("bound historical input changed")
            files.add(path)
            for adjacent in ("results.jsonl", "RESULT.json", "TERMINAL.json", "MANIFEST.json", "manifest.json"):
                if (path.parent / adjacent).is_file():
                    files.add(path.parent / adjacent)
    # Adjacent raw historical results retain their journals when those original
    # journals are still available; no old experiment or archive is rewritten.
    missing_journals = []
    for result_file in [path for path in files if path.name == "results.jsonl"]:
        parts = result_file.parts
        indices = [i for i in range(len(parts) - 2) if parts[i:i + 3] == ("artifacts", "v5", "evaluations")]
        if not indices:
            continue
        run_root = Path(*parts[:indices[-1]])
        with result_file.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                journal = json.loads(line).get("attempt_journal")
                if not journal:
                    continue
                path = (run_root / journal["path"]).resolve()
                if not path.is_relative_to(ROOT):
                    raise ValueError("historical journal path escapes workspace")
                if path.is_file():
                    if pack.digest_file(path) != journal["sha256"]:
                        raise ValueError("historical journal hash changed")
                    files.add(path)
                else:
                    missing_journals.append(workspace_relative(path))
    selected = sorted(path for path in files if selected_file(path))
    if not runtime_files <= set(selected):
        raise ValueError("authoritative runtime contains excluded files; cannot preserve its identity")
    return selected, {"bound_history_indexes": sorted(workspace_relative(path) for path in history_indexes),
        "sealed_candidate_directories": sorted(workspace_relative(path) for path in candidates),
        "required_old_runtime_directories": sorted(workspace_relative(path) for path in revisions),
        "generation_cost_and_reuse_bindings": generation_bindings,
        "historical_journals_not_available": sorted(set(missing_journals))}


def write_archive(path, files, virtual, snapshot, secrets):
    inventory, stats = [], {}
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for i, source in enumerate(files, 1):
            name = source.relative_to(ROOT).as_posix()
            safe_path(name)
            before = source.stat()
            stats[source] = (before.st_size, before.st_mtime_ns)
            digest, tail = hashlib.sha256(), b""
            with source.open("rb") as stream, archive.open(pack.PREFIX + name, "w", force_zip64=True) as target:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    scan_blob(tail + chunk, name if source.suffix.lower() != ".zip" else name + ".raw", secrets)
                    digest.update(chunk)
                    target.write(chunk)
                    tail = (tail + chunk)[-4096:]
            if source.suffix.lower() == ".zip":
                scan_blob(source.read_bytes(), name, secrets)
            inventory.append({"path": name, "bytes": before.st_size, "sha256": digest.hexdigest()})
            if i % 2000 == 0:
                print(json.dumps({"phase": "package", "files": i, "total": len(files)}), flush=True)
        for name, data in virtual.items():
            safe_path(name)
            if name in {row["path"] for row in inventory}:
                raise ValueError("virtual/source member collision")
            scan_blob(data, name, secrets)
            archive.writestr(pack.PREFIX + name, data)
            inventory.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        for source, before in stats.items():
            after = source.stat()
            if (after.st_size, after.st_mtime_ns) != before:
                raise ValueError("file changed during handoff packaging")
        for name, value in (("FILES.json", inventory), ("EXCLUDED.json", EXCLUDED), ("SNAPSHOT.json", snapshot)):
            data = pack.json_bytes(value)
            scan_blob(data, name, secrets)
            archive.writestr(pack.META + name, data)
    return inventory


def verify_archive(path, secrets=()):
    result = pack.verify(path)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read(pack.META + "SNAPSHOT.json"))
        inventory = {row["path"]: row for row in json.loads(archive.read(pack.META + "FILES.json"))}
        for name in archive.namelist():
            scan_blob(archive.read(name), name, secrets)
        def bound(name, digest):
            safe_path(name)
            if name not in inventory or inventory[name]["sha256"] != digest:
                raise ValueError("missing or changed bound archive evidence: " + name)
        for index in manifest.get("bound_history_indexes", []):
            for name, digest in json.loads(archive.read(pack.PREFIX + index))["source_sha256"].items():
                bound(name, digest)
        for binding in manifest.get("generation_cost_and_reuse_bindings", {}).values():
            for name, digest in binding["files"].items():
                bound(name, digest)
        for directory in manifest.get("sealed_candidate_directories", []):
            row = json.loads(archive.read(pack.PREFIX + directory + "/RESULT.json"))
            seal = json.loads(archive.read(pack.PREFIX + directory + "/TERMINAL.json"))
            if canonical_sha256(row) != seal["result_sha256"] or ("result" in seal and seal["result"] != row):
                raise ValueError("candidate result seal changed")
            for name, digest in row["evidence_sha256"].items():
                bound(directory + "/" + name, digest)
        for name in inventory:
            if not name.endswith("/AUDIT_PACKET.json"):
                continue
            packet = json.loads(archive.read(pack.PREFIX + name))
            binding = packet["source_binding"]
            source = workspace_relative(binding["directory"], manifest["original_workspace"])
            for file, digest in binding["files"].items():
                bound(source + "/" + file, digest)
    result.update(secret_scan="PASS", historical_source_bindings="PASS", candidate_seals="PASS",
                  audit_source_bindings="PASS", generation_cost_and_reuse_bindings="PASS", provider_calls=0)
    return result


def verify_extracted(extracted, out_relative, result_path):
    """Execute the extracted CLI, Replay and zero-call resume using package members only."""
    script = extracted / "scripts/v5/verify_development_factory.py"
    if not script.is_file() or result_path.exists():
        raise ValueError("extracted verifier missing or immutable verification output already exists")
    subprocess.run([sys.executable, "-B", str(script), "--root", str(extracted),
        "--out", str(extracted / out_relative), "--protection-scope", "included", "--result", str(result_path)],
        check=True, cwd=extracted, capture_output=True, text=True)
    result = read(result_path)
    if (result.get("status") != "PASS" or result.get("provider_calls") != 0
            or result.get("ledger_unchanged") is not True or result.get("required_positive_replays") != "PASS"
            or result.get("actual_cli_resume", {}).get("status") != "PASS"):
        raise ValueError("extracted Replay/resume verification did not pass")
    return result


def build(out=DEFAULT_OUT, output=DEFAULT_OUTPUT, name=DEFAULT_NAME):
    out, output = Path(out).resolve(), Path(output).resolve()
    if not out.is_relative_to(ROOT / "artifacts/v5/data_factory/dev_auto_audit") or not output.is_relative_to(ROOT / "exports"):
        raise ValueError("isolated development/output roots required")
    if Path(name).name != name or not name.endswith(".zip"):
        raise ValueError("archive name must be a zip basename")
    output.mkdir(parents=True, exist_ok=True)
    destination, temporary = output / name, output / (name + ".partial")
    if destination.exists() or temporary.exists() or any((output / name).exists() for name in (
            "DELIVERY_VERIFICATION.json", "EXTRACTED_VERIFICATION.json")):
        raise ValueError("handoff outputs are immutable; select a new output version")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT)
    if dirty.strip():
        raise ValueError("commit tracked source changes before final packaging")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    identity = {"head": head, "baseline_commit": BASELINE, "tracked_worktree_clean": True,
                "push_performed": False, "unrelated_untracked_files": "EXCLUDED"}
    diff = subprocess.check_output(["git", "diff", "--binary", BASELINE + ".." + head, "--",
                                   *sorted(CODE_FOLDERS), *sorted(ROOT_FILES)], cwd=ROOT)
    files, bindings = selection(out)
    snapshot = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "kind": "DEVELOPMENT_AUTO_AUDITED",
        "formal_accepted": False, "same_model_audit_independent_science": False, "provider_calls": 0,
        "original_workspace": ROOT.as_posix(), "runtime_sha256": source_tree_hash(ROOT), "git_head": head,
        "read_first": out.relative_to(ROOT).as_posix() + "/ROUND_REPORT.md", **bindings}
    virtual = {"handoff/GIT_IDENTITY.json": pack.json_bytes(identity), "handoff/GIT_DIFF.patch": diff,
               "handoff/MANIFEST.json": pack.json_bytes(snapshot)}
    secrets = known_secrets()
    write_archive(temporary, files, virtual, snapshot, secrets)
    if selection(out)[0] != files:
        raise ValueError("handoff source membership changed during packaging")
    verification = verify_archive(temporary, secrets)
    with tempfile.TemporaryDirectory(prefix="ioa-dev-handoff-") as temporary_root:
        with zipfile.ZipFile(temporary) as archive:
            archive.extractall(temporary_root)
        extracted = Path(temporary_root) / "ioa_codex_spec"
        if source_tree_hash(extracted) != snapshot["runtime_sha256"]:
            raise ValueError("extracted authoritative runtime differs")
        revisions = list((extracted / out.relative_to(ROOT) / "source_revisions").iterdir())
        revisions += [extracted / name for name in bindings["required_old_runtime_directories"]]
        for revision in revisions:
            if revision.is_dir() and source_tree_hash(revision) != revision.name:
                raise ValueError("retained source revision incomplete")
        extracted_receipt = output / "EXTRACTED_VERIFICATION.json"
        extracted_verification = verify_extracted(extracted, out.relative_to(ROOT), extracted_receipt)
        scan_blob(extracted_receipt.read_bytes(), extracted_receipt.name, secrets)
    temporary.rename(destination)
    verification.update(status="PASS", archive=destination.name, sha256=pack.digest_file(destination),
        bytes=destination.stat().st_size, git_head=head, extracted_runtime_sha256=snapshot["runtime_sha256"],
        source_revisions_checked=len(revisions), extracted_runtime="PASS", strict_replay_execution="PASS",
        actual_extracted_cli_resume="PASS", extracted_verification=extracted_receipt.name,
        extracted_verification_sha256=pack.digest_file(extracted_receipt),
        extracted_strict_replay_count=extracted_verification["strict_replay_count"],
        protected_history=extracted_verification["protected_history"])
    (output / (name + ".sha256")).write_text(verification["sha256"] + "  " + name + "\n", encoding="ascii")
    (output / "DELIVERY_VERIFICATION.json").write_bytes(pack.json_bytes(verification))
    print(json.dumps(verification, ensure_ascii=False), flush=True)
    return verification


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive-name", default=DEFAULT_NAME)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_archive(args.verify, known_secrets()), ensure_ascii=False))
    else:
        with writer_lock(ROOT / "artifacts/v5/data_factory"), writer_lock(args.out.resolve()):
            build(args.out, args.output, args.archive_name)
