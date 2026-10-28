"""Build the external technical-review handoff (zero paid calls, zero network).

Outputs under exports/tree-factory-review-20261024/:
  IoA-Bench-v5-TreeFactory-SOURCE-REVIEW-20261024.zip   (HEAD source + goal pack + git diffs)
  IoA-Bench-v5-TreeFactory-EVIDENCE-20261024.zip        (full run dir + sealed index + inventory)
  REVIEW_FILE_INDEX.json / PACKAGE_VERIFICATION.json

Never mutates originals: staging copies only; secrets (if any) are redacted in
the STAGED copy and logged. STOP.json, the request ledger and every sealed
terminal are copied verbatim.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "exports/tree-factory-review-20261024"
STAGE = OUT / "_stage"
VERIFY = OUT / "_verify"
RUN = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
GOAL_PACK = ROOT / "docs/plans/zcode_tree_factory_20261024"
BASELINE_COMMIT = "adc1570"  # pre-round baseline (packaged handoff base + state-only commit)
SEALED_INDEX = ROOT / ("artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/"
                       "f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json")
PRIOR_INVENTORY = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/PROTECTED_BASELINE.json"
SOURCE_ZIP = OUT / "IoA-Bench-v5-TreeFactory-SOURCE-REVIEW-20261024.zip"
EVIDENCE_ZIP = OUT / "IoA-Bench-v5-TreeFactory-EVIDENCE-20261024.zip"
SECRET_PATTERNS = (b"sk-f5eub", b"AIHUBMIX_API_KEY=", b"Bearer sk-", b"DEEPSEEK_API_KEY=")
REDACT_WITH = b"[REDACTED-SECRET]"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def stage_source(stage: Path) -> list[Path]:
    source = stage / "source"
    source.mkdir(parents=True)
    # exact HEAD bytes via git archive (tracked tree == HEAD, verified clean)
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT,
                             capture_output=True, check=True).stdout
    tar = stage / "_head.tar"
    tar.write_bytes(archive)
    shutil.unpack_archive(str(tar), str(source))
    tar.unlink()
    # the goal pack is untracked on purpose; add it verbatim from disk
    pack = source / "review-goal-pack"
    shutil.copytree(GOAL_PACK, pack)
    review = source / "review-git"
    review.mkdir()
    (review / "HEAD.txt").write_text(git("rev-parse", "HEAD"), encoding="utf-8")
    (review / "branch.txt").write_text(git("rev-parse", "--abbrev-ref", "HEAD"), encoding="utf-8")
    (review / "log-stat-adc1570..HEAD.txt").write_text(
        git("log", "--stat", f"{BASELINE_COMMIT}..HEAD"), encoding="utf-8")
    (review / "diff-adc1570..HEAD.patch").write_text(
        git("diff", f"{BASELINE_COMMIT}..HEAD"), encoding="utf-8")
    (review / "status-short.txt").write_text(git("status", "--short"), encoding="utf-8")
    return sorted(p for p in source.rglob("*") if p.is_file())


def stage_evidence(stage: Path) -> list[Path]:
    evidence = stage / "evidence"
    evidence.mkdir(parents=True)
    shutil.copytree(RUN, evidence / "run", ignore=shutil.ignore_patterns("__pycache__"))
    history = evidence / "sealed-history-index"
    history.mkdir()
    shutil.copy2(SEALED_INDEX, history / SEALED_INDEX.name)
    protection = evidence / "protection"
    protection.mkdir()
    shutil.copy2(PRIOR_INVENTORY, protection / "prior-PROTECTED_BASELINE.json")
    return sorted(p for p in evidence.rglob("*") if p.is_file())


def scan_and_redact(files: list[Path]) -> dict:
    """Redact real secrets in STAGED copies; self-referential detection literals
    that match only because a scanner embeds the pattern are recorded, and only
    genuine key material (prefix literals, bearer values, valued assignments)
    triggers redaction."""
    import re
    findings, redacted, deviations = [], [], []
    valued_assignment = re.compile(rb"(AIHUBMIX_API_KEY|DEEPSEEK_API_KEY)=([^\s\"']{8,})")
    for path in files:
        data = path.read_bytes()
        changed = False
        for literal in (b"sk-f5eub", b"Bearer sk-"):
            if literal in data:
                findings.append({"file": str(path), "pattern": literal.decode(),
                                 "reason": "key-prefix or bearer literal"})
                data = data.replace(literal, REDACT_WITH)
                changed = True
        for match in valued_assignment.finditer(data):
            value = match.group(2)
            if value.startswith(b"your") or value == b"[REDACTED-SECRET]":
                continue
            findings.append({"file": str(path),
                             "pattern": match.group(1).decode() + "=<valued>",
                             "reason": "assignment with a non-placeholder value"})
            data = data.replace(match.group(0), match.group(1) + b"=" + REDACT_WITH)
            changed = True
        if changed:
            path.write_bytes(data)
            redacted.append(str(path))
            deviations.append({
                "file": str(path.relative_to(STAGE)),
                "note": "staged copy redacted; HEAD bytes differ only in the listed literals",
                "post_redaction_sha256": sha256_bytes(data)})
    return {"status": "REDACTED" if findings else "PASS",
            "staged_files_scanned": len(files), "findings": findings,
            "staged_copies_redacted": redacted, "per_file_deviations": deviations,
            "originals_touched": False}


def categorize(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.startswith(("src/", "tests/", "scripts/", "config/", "contracts/")):
        return "source:" + rel.split("/", 1)[0]
    if rel.startswith(("docs/", "state/", "review-goal-pack/", "review-git/", "assets/",
                       "adr/", "roles/", "WORKSPACE")):
        return "docs-or-state"
    if "/ab/candidates/" in rel:
        return "evidence:ab-candidate"
    if "/ab/reviews/" in rel:
        return "evidence:ab-review"
    if "/minimal/" in rel:
        return "evidence:minimal-online"
    if "/scratch/" in rel:
        return "evidence:scratch-diagnostics"
    if rel.startswith("evidence/sealed-history-index/"):
        return "evidence:sealed-dedup-index"
    if rel.startswith("evidence/protection/"):
        return "evidence:protection-inventory"
    if "REQUEST_LEDGER" in rel or "STOP" in rel:
        return "evidence:ledger-or-stop"
    if rel.endswith((".xml",)):
        return "evidence:regression"
    return "evidence:run-artifact"


def zip_tree(stage_root: Path, zip_path: Path, index: list, zip_label: str):
    members = {}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in stage_root.rglob("*"):
            if not path.is_file():
                continue
            arc = path.relative_to(stage_root).as_posix()
            bundle.write(path, arc)
            data = path.read_bytes()
            digest = sha256_bytes(data)
            members[arc] = digest
            index.append({"zip": zip_label, "path": arc, "bytes": len(data),
                          "sha256": digest, "category": categorize(path, stage_root)})
    return members


def verify_zip(zip_path: Path, members: dict) -> dict:
    with zipfile.ZipFile(zip_path) as bundle:
        bad = bundle.testzip()
        bundle.extractall(VERIFY)
    mismatches = []
    for arc, digest in members.items():
        extracted = VERIFY / arc
        if not extracted.is_file() or sha256_bytes(extracted.read_bytes()) != digest:
            mismatches.append(arc)
    shutil.rmtree(VERIFY, ignore_errors=True)
    return {"zip_crc_testzip": "PASS" if bad is None else f"FAIL:{bad}",
            "members": len(members),
            "full_extraction_sha_verified": len(members) - len(mismatches),
            "mismatches": mismatches[:20]}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in (STAGE, VERIFY):
        shutil.rmtree(stale, ignore_errors=True)
    STAGE.mkdir(parents=True)
    source_files = stage_source(STAGE)
    evidence_files = stage_evidence(STAGE)
    all_staged = source_files + evidence_files
    secret_report = scan_and_redact(all_staged)
    index: list[dict] = []
    source_members = zip_tree(STAGE / "source", SOURCE_ZIP, index, "SOURCE")
    evidence_members = zip_tree(STAGE / "evidence", EVIDENCE_ZIP, index, "EVIDENCE")
    verification = {
        "version": "ioabench.v5.review-package-verification/1.0.0",
        "generated_utc": utc(),
        "git_head": git("rev-parse", "HEAD").strip(),
        "git_branch": git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "baseline_commit_for_diff": BASELINE_COMMIT,
        "tracked_tree_clean": not [line for line in git("status", "--short").splitlines()
                                   if not line.startswith("??")],
        "runtime_source_sha256": __import__("ioabench.runtime.full_manifest",
                                             fromlist=["source_tree_hash"]).source_tree_hash(ROOT),
        "source_zip": {"path": SOURCE_ZIP.name, "bytes": SOURCE_ZIP.stat().st_size,
                       "sha256": sha256_bytes(SOURCE_ZIP.read_bytes()),
                       **verify_zip(SOURCE_ZIP, source_members)},
        "evidence_zip": {"path": EVIDENCE_ZIP.name, "bytes": EVIDENCE_ZIP.stat().st_size,
                         "sha256": sha256_bytes(EVIDENCE_ZIP.read_bytes()),
                         **verify_zip(EVIDENCE_ZIP, evidence_members)},
        "secret_scan": secret_report,
        "exclusions": [
            "exports/ prior handoff zips (superseded by this package; paths listed in report)",
            "artifacts/v5/data_factory/dev_auto_audit/round-20261020 full 1.9 GB prior-round "
            "workspace (only its sealed dedup index and protected inventory are included; the "
            "round stays independently reviewable via the 2026-10-20 handoff zip)",
            "workspace .env (secret; boolean presence recorded in BASELINE.json)",
            "all 180,204 protected history FILES (hash inventory + verification receipt included "
            "instead; the zip is NOT the full history database)"],
        "network_calls": 0, "provider_calls": 0, "paid_requests": 0}
    (OUT / "REVIEW_FILE_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8")
    (OUT / "PACKAGE_VERIFICATION.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(STAGE, ignore_errors=True)
    print(json.dumps({"source_members": len(source_members),
                      "evidence_members": len(evidence_members),
                      "source_zip_mb": round(SOURCE_ZIP.stat().st_size / 1_048_576, 2),
                      "evidence_zip_mb": round(EVIDENCE_ZIP.stat().st_size / 1_048_576, 2),
                      "secret_scan": secret_report["status"],
                      "findings": len(secret_report["findings"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
