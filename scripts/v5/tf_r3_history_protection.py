"""R3 history protection: hash-verify the frozen R1/R2 universe (real counts).

The R2 evidence reported ``files_checked=0`` while claiming protection. This
script enumerates the ACTUAL protected universe of this round — the sealed R1
run, the sealed R2 run (including every accepted candidate's evidence dir) and
the sealed history index — and records per-file SHA-256 with real counts. The
manifest is written next to the baseline; mismatches abort with detail.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"
R1 = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
R2 = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"
SEALED_INDEX = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_universe() -> dict[str, list[Path]]:
    frozen = json.loads((RUN / "FROZEN_REFERENCES.json").read_text(encoding="utf-8"))
    universe: dict[str, list[Path]] = {}
    r1_dirs = [ROOT / entry["evidence_dir"] for entry in frozen["r1_sealed"]["candidates"]
               if entry.get("evidence_dir")]
    universe["r1_run_root_files"] = [p for p in R1.glob("*") if p.is_file()]
    universe["r1_accepted_candidate_evidence"] = [
        p for d in r1_dirs if d.exists() for p in d.rglob("*") if p.is_file()]
    universe["r2_run_root_files"] = [p for p in R2.glob("*") if p.is_file()]
    r2_dirs = [R2 / row["evidence"] for row in [
        json.loads(line) for line in (R2 / "DEV_POOL_INDEX.jsonl").read_text(encoding="utf-8").splitlines()]]
    universe["r2_accepted_candidate_evidence"] = [
        p for d in r2_dirs if d.exists() for p in d.rglob("*") if p.is_file()]
    universe["sealed_history_index"] = [SEALED_INDEX]
    universe["frozen_references"] = [RUN / "FROZEN_REFERENCES.json"]
    return universe


def main() -> int:
    universe = protected_universe()
    manifest: dict = {
        "version": "ioabench.v5.r3.history-protection/1.0.0",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "READ_ONLY hash verification of the frozen R1/R2 universe; no file "
                  "under protection is opened for write",
        "groups": {}, "files_checked": 0, "bytes_checked": 0,
        "mismatches": [], "exclusions": []}
    for group, paths in universe.items():
        rows = {}
        for path in sorted(paths):
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            rows[rel] = sha256(path)
            manifest["files_checked"] += 1
            manifest["bytes_checked"] += path.stat().st_size
        manifest["groups"][group] = {"files": len(rows), "sha256_by_file": rows}
    baseline = json.loads((RUN / "HISTORY_PROTECTION_R3.json").read_text(encoding="utf-8"))
    baseline_count = 0
    for group in baseline["groups"].values():
        for rel, expected in group["sha256_by_file"].items():
            path = ROOT / rel
            actual = sha256(path) if path.is_file() else None
            baseline_count += 1
            if actual != expected:
                manifest["mismatches"].append({"file": rel, "expected": expected, "actual": actual})
    manifest["baseline_files_rechecked"] = baseline_count
    # cross-check the anchors recorded at baseline time
    frozen = json.loads((RUN / "FROZEN_REFERENCES.json").read_text(encoding="utf-8"))
    for entry in frozen["r2_sealed"]["candidates"]:
        rel = (R2 / entry["evidence_dir"] / "TERMINAL.json").relative_to(ROOT).as_posix()
        recorded = entry.get("terminal.json_sha256")
        actual = manifest["groups"]["r2_accepted_candidate_evidence"]["sha256_by_file"].get(rel)
        if recorded and recorded != actual:
            manifest["mismatches"].append({"file": rel, "expected": recorded, "actual": actual})
    r1_map = manifest["groups"]["r1_accepted_candidate_evidence"]["sha256_by_file"]
    for entry in frozen["r1_sealed"]["candidates"]:
        rel = (ROOT / entry["evidence_dir"] / "TERMINAL.json").relative_to(ROOT).as_posix()
        recorded = entry.get("terminal.json_sha256")
        actual = r1_map.get(rel)
        if recorded and recorded != actual:
            manifest["mismatches"].append({"file": rel, "expected": recorded, "actual": actual})
    (RUN / "closure/HISTORY_PROTECTION_FINAL.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"files_checked": manifest["files_checked"],
                      "bytes_checked": manifest["bytes_checked"],
                      "groups": {k: v["files"] for k, v in manifest["groups"].items()},
                      "mismatches": len(manifest["mismatches"])}, ensure_ascii=False))
    return 1 if manifest["mismatches"] or not baseline_count or not manifest["files_checked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
