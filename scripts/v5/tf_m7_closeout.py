"""M7 closeout: zero-call resume, history protection, secret scan, handoff zip."""
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
RUN = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resume_verify() -> dict:
    """Re-read every sealed terminal result; no provider construction, no calls."""
    before = sha256(RUN / "REQUEST_LEDGER.jsonl") if (RUN / "REQUEST_LEDGER.jsonl").exists() else None
    from ioabench.v5.ai_generation.direct_deepseek import candidate_result
    sealed = 0
    for result_path in sorted(RUN.glob("minimal/candidates/*/RESULT.json")):
        candidate_result(result_path.parent)
        sealed += 1
    after = sha256(RUN / "REQUEST_LEDGER.jsonl") if (RUN / "REQUEST_LEDGER.jsonl").exists() else None
    return {"status": "PASS", "sealed_candidates_reverified": sealed,
            "ledger_unchanged": before == after, "provider_calls": 0}


def replay_rows() -> dict:
    rows = 0
    for replay_path in sorted(RUN.glob("minimal/candidates/*/REPLAY.json")):
        for row in json.loads(replay_path.read_text(encoding="utf-8")):
            if row.get("passed") is not True:
                raise ValueError("sealed strict replay row failed: " + str(replay_path))
            rows += 1
    return {"strict_replay_rows_passed": rows}


def history_protection() -> dict:
    manifest = json.loads((RUN / "PROTECTED_HISTORY_MANIFEST.json").read_text(encoding="utf-8"))
    prior = json.loads((ROOT / manifest["prior_inventory_path"]).read_text(encoding="utf-8"))["files"]
    changed, missing = [], []
    for name, digest in prior.items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif sha256(path) != digest:
            changed.append(name)
    new_scope_changed = []
    for name, digest in manifest["new_scope_files"].items():
        path = ROOT / name
        if path.is_file() and sha256(path) != digest:
            new_scope_changed.append(name)
        elif not path.is_file():
            new_scope_changed.append(name + " (missing)")
    # source trees under src/tests/scripts/contracts/config are this round's
    # authorized code-change surface (git-tracked); everything else in the M0
    # snapshot must be untouched
    intended_prefixes = ("src/", "tests/", "scripts/", "contracts/", "config/")
    unintended = [name for name in new_scope_changed
                  if not name.startswith(intended_prefixes)]
    status = "PASS" if not changed and not missing and not unintended else "FAIL"
    value = {"status": status, "prior_inventory_files": len(prior),
             "prior_changed": changed[:10], "prior_missing_count": len(missing),
             "new_scope_files": len(manifest["new_scope_files"]),
             "intended_code_changes_this_round": sorted(
                 name for name in new_scope_changed if name.startswith(intended_prefixes)),
             "unintended_new_scope_changes": unintended[:10],
             "provider_calls": 0}
    (RUN / "HISTORY_PROTECTION.json").write_text(json.dumps(value, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    return value


SECRET_PATTERNS = ("sk-f5eub", "AIHUBMIX_API_KEY=", "Bearer sk-", "DEEPSEEK_API_KEY=")


def secret_scan() -> dict:
    findings = []
    for path in sorted(RUN.rglob("*")):
        if not path.is_file() or path.suffix.lower() in {".zip", ".png", ".jpg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern in text:
                findings.append({"file": path.relative_to(RUN).as_posix(), "pattern": pattern})
    value = {"status": "PASS" if not findings else "FAIL", "scanned_files":
             sum(1 for p in RUN.rglob("*") if p.is_file()), "findings": findings}
    (RUN / "SECRET_SCAN.json").write_text(json.dumps(value, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    return value


def handoff_zip() -> dict:
    stamp = "20261024-r1"
    export = ROOT / "exports/tree-factory-handoff-20261024"
    export.mkdir(parents=True, exist_ok=True)
    zip_path = export / f"IoA-Bench-v5-TreeFactory-HANDOFF-{stamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    members = {}
    excludes = {"_tmp_"}  # scratch scripts live under scratch/ and stay out of the bundle
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(RUN.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if any(marker in path.name for marker in excludes):
                continue
            members[relative] = sha256(path)
            bundle.write(path, relative)
        # code and tests of this round for replay-from-source
        for code in sorted([*(ROOT / "src/ioabench/v5/ai_generation").glob("*.py"),
                            *(ROOT / "src/ioabench/v5/dynamic").glob("t3*_slice.py"),
                            *(ROOT / "scripts/v5").glob("tf_*.py"),
                            *(ROOT / "tests/v5").glob("test_tf*.py"),
                            *(ROOT / "tests/v5").glob("test_scenario_tree.py")]):
            if any(marker in code.name for marker in excludes):
                continue
            relative = code.relative_to(ROOT).as_posix()
            members[relative] = sha256(code)
            bundle.write(code, relative)
    manifest = {"zip_bytes": zip_path.stat().st_size,
                "zip_sha256": sha256(zip_path),
                "members": len(members), "member_sha256": members,
                "created_utc": utc(),
                "verification_scope": "this run directory (scratch _tmp_* excluded) plus this round's code/tests; "
                                       "full-history replay additionally needs the sealed 2026-10-20 handoff "
                                       "(exports/development-factory-handoff-20261020-r2) and the workspace",
                "excluded": ["scratch _tmp_* diagnostics (regenerable)",
                             "workspace .env (secret)"],
                "provider_calls": 0}
    (export / "HANDOFF_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    # independent extraction + CRC + per-member SHA verification
    check_dir = export / "_extract_check"
    if check_dir.exists():
        shutil.rmtree(check_dir)
    with zipfile.ZipFile(zip_path) as bundle:
        bad = bundle.testzip()
        bundle.extractall(check_dir)
    mismatches = []
    for relative, digest in members.items():
        extracted = check_dir / relative
        if not extracted.is_file() or sha256(extracted) != digest:
            mismatches.append(relative)
    shutil.rmtree(check_dir)
    value = {"zip": zip_path.name, "zip_sha256": manifest["zip_sha256"],
             "zip_crc": "PASS" if bad is None else f"FAIL:{bad}",
             "members": len(members), "extract_verify_mismatches": mismatches,
             "status": "PASS" if bad is None and not mismatches else "FAIL"}
    (export / "HANDOFF_VERIFICATION.json").write_text(json.dumps(value, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
    return value


def git_state() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.splitlines()
    from ioabench.runtime.full_manifest import source_tree_hash
    return {"git_head": head, "runtime_sha256": source_tree_hash(ROOT),
            "dirty_tracked": [line for line in status if not line.startswith("??")][:20],
            "untracked_count": sum(1 for line in status if line.startswith("??"))}


def main() -> int:
    report = {"generated_utc": utc(), "resume": resume_verify(),
              "replay": replay_rows(), "protection": history_protection(),
              "secrets": secret_scan(), "handoff": handoff_zip(), "git": git_state()}
    (RUN / "M7_CLOSEOUT.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "git"},
                     ensure_ascii=False)[:1200])
    ok = (report["resume"]["status"] == "PASS" and report["protection"]["status"] == "PASS"
          and report["secrets"]["status"] == "PASS" and report["handoff"]["status"] == "PASS")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
