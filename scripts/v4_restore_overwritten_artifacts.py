"""Restore workspace artifacts that mock/test runs overwrote.

A mock CLI run and the test suite rewrote gate/smoke artifacts with mock data
(`model: mock`, pytest temp paths). These are frozen historical evidence and
must be restored byte-exactly. Sources are tried in order: the 2026-09-29
handoff archive, then the 2026-09-30 final-delivery archive.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path("D:/Project/ioa_codex_spec")
BASELINE = json.loads((ROOT / "artifacts/scientific_closure_v3_2/baseline.json").read_text(encoding="utf-8"))["files"]
ARCHIVES = [ROOT / "archive/deliveries/IoA-Bench-current-workspace-handoff-20260929-latest.zip",
            ROOT / "archive/deliveries/IoA-Bench-v3-20260930-final-delivery.zip"]

report = {"restored": [], "missing": [], "unchanged": []}
for rel, expected in BASELINE.items():
    if rel.startswith(("src/", "contracts/", "config/")):
        continue
    path = ROOT / rel
    current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if current == expected:
        continue
    found = False
    for archive in ARCHIVES:
        if not archive.is_file():
            continue
        with ZipFile(archive) as zf:
            names = set(zf.namelist())
            for candidate in (rel, rel.replace("/", "\\")):
                if candidate in names:
                    data = zf.read(candidate)
                    if hashlib.sha256(data).hexdigest() == expected:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                        report["restored"].append({"path": rel, "source": archive.name})
                        found = True
                    break
        if found:
            break
    if not found:
        report["missing"].append({"path": rel, "expected": expected, "current": current})

print(json.dumps({"restored": len(report["restored"]), "unrecoverable": len(report["missing"])}, indent=1))
for m in report["missing"]:
    print("  UNRECOVERABLE:", m["path"])
report_dir = ROOT / "artifacts/scientific_closure_v4"
index = 1
while (report_dir / f"workspace-restore-{index:03d}.json").exists():
    index += 1
with (report_dir / f"workspace-restore-{index:03d}.json").open("x", encoding="utf-8", newline="\n") as stream:
    json.dump({"artifact": "V4_WORKSPACE_ARTIFACT_RESTORE", **report}, stream,
              ensure_ascii=False, indent=2, sort_keys=True)
    stream.write("\n")
