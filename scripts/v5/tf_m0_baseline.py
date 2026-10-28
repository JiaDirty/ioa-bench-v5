"""Tree-factory M0: baseline, protected-history manifest and key presence (boolean only).

Read-only over user history; writes only under artifacts/v5/tree_factory/<run_id>.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

RUN_ID = "tf-20261024-r1"
OUT = ROOT / "artifacts" / "v5" / "tree_factory" / RUN_ID
PRIOR_INVENTORY = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/PROTECTED_BASELINE.json"
GOAL_PACK = ROOT / "docs/plans/zcode_tree_factory_20261024"
PACKAGED_BASELINE_HEAD = "ad9e4f4236917d52b35e65d8286317c8e0d79641"
PACKAGED_RUNTIME_SHA = "79728d820ded19e8c1b83cf040e75c9fed16f7464c9208363277dcd915e463c8"
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".git", ".zcode", ".workbuddy-ai", "node_modules"}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(payload) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.splitlines()
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", PACKAGED_BASELINE_HEAD, head],
                              cwd=ROOT).returncode == 0
    from ioabench.runtime.full_manifest import source_tree_hash
    runtime_sha = source_tree_hash(ROOT)

    goal_files = {}
    for path in sorted(GOAL_PACK.rglob("*")):
        if path.is_file():
            goal_files[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    packaged_manifest = json.loads((GOAL_PACK / "FILE_SHA256.json").read_text(encoding="utf-8"))
    packaged_files = packaged_manifest.get("files", packaged_manifest)
    pack_prefix = GOAL_PACK.relative_to(ROOT).as_posix() + "/"
    pack_mismatches, pack_missing, pack_extra = [], [], []
    for name, digest in packaged_files.items():
        if not isinstance(digest, dict) or "sha256" not in digest:
            pack_mismatches.append(pack_prefix + name)
            continue
        path = ROOT / pack_prefix / name
        if not path.is_file():
            pack_missing.append(pack_prefix + name)
        elif sha256_file(path) != digest["sha256"] or path.stat().st_size != digest.get("size_bytes"):
            pack_mismatches.append(pack_prefix + name)
    listed = {pack_prefix + name for name in packaged_files}
    pack_extra = sorted(path for path in goal_files
                        if Path(path).name != "FILE_SHA256.json" and path not in listed)

    key_env = bool(os.environ.get("AIHUBMIX_API_KEY"))
    key_dotenv = False
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("AIHUBMIX_API_KEY="):
                key_dotenv = True

    baseline = {
        "version": "ioabench.v5.tree-factory-baseline/1.0.0", "run_id": RUN_ID,
        "created_utc": started, "project_git_head": head, "git_branch": branch,
        "git_status_short": status,
        "packaged_baseline_head": PACKAGED_BASELINE_HEAD,
        "packaged_baseline_is_ancestor": ancestor,
        "runtime_source_sha256": runtime_sha,
        "runtime_matches_packaged_baseline": runtime_sha == PACKAGED_RUNTIME_SHA,
        "goal_pack_files": goal_files, "goal_pack_manifest_mismatches": pack_mismatches,
        "goal_pack_manifest_missing": pack_missing, "goal_pack_manifest_extra": pack_extra,
        "aihubmix_key_env_var_present": key_env, "aihubmix_key_dotenv_entry_present": key_dotenv,
        "note": "key values are never read, hashed or logged by this script",
    }

    prior = json.loads(PRIOR_INVENTORY.read_text(encoding="utf-8"))
    prior_files = prior["files"]
    changed, missing = [], []
    for name, digest in prior_files.items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif sha256_file(path) != digest:
            changed.append(name)
    new_scope = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or EXCLUDED_PARTS & set(path.parts):
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in prior_files or relative.startswith("artifacts/v5/tree_factory/"):
            continue
        new_scope[relative] = sha256_file(path)
    manifest = {
        "version": "ioabench.v5.tree-factory-protected-history/1.0.0", "run_id": RUN_ID,
        "created_utc": started,
        "prior_inventory_path": PRIOR_INVENTORY.relative_to(ROOT).as_posix(),
        "prior_inventory_sha256": sha256_file(PRIOR_INVENTORY),
        "prior_inventory_file_count": len(prior_files),
        "prior_inventory_changed": changed, "prior_inventory_missing": missing,
        "new_scope_file_count": len(new_scope), "new_scope_files": new_scope,
        "exclusions": sorted(EXCLUDED_PARTS) + ["artifacts/v5/tree_factory/ (this run)"],
        "verification": "PASS" if not changed and not missing else "FAIL",
    }
    (OUT / "PROTECTED_HISTORY_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    baseline["protected_history"] = {
        "manifest": "PROTECTED_HISTORY_MANIFEST.json",
        "prior_inventory_verified": manifest["verification"],
        "prior_inventory_changed_count": len(changed),
        "prior_inventory_missing_count": len(missing),
        "new_scope_file_count": len(new_scope)}
    baseline["baseline_sha256"] = canonical(baseline)
    (OUT / "BASELINE.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(json.dumps({"run_id": RUN_ID, "head": head, "ancestor_ok": ancestor,
                      "runtime_matches": runtime_sha == PACKAGED_RUNTIME_SHA,
                      "pack_mismatches": pack_mismatches, "key_env": key_env,
                      "key_dotenv": key_dotenv, "prior_verified": manifest["verification"],
                      "prior_changed": len(changed), "prior_missing": len(missing),
                      "new_scope_files": len(new_scope)}, ensure_ascii=False))
    return 0 if manifest["verification"] == "PASS" and not pack_mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
