"""Reconcile pilot gates against dataset versions on disk (authoritative)."""
import json
import os
import time
from pathlib import Path

ROOT = Path(".")
ORDER = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
         "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")

# 1) dataset versions on disk per suite (newest first)
print("== dataset versions on disk ==")
on_disk = {}
for suite in ORDER:
    versions = []
    base = ROOT / "data" / "datasets" / suite
    if base.is_dir():
        for entry in base.iterdir():
            if entry.is_dir() and (entry / "cases.jsonl").is_file():
                versions.append((entry.name, entry.stat().st_mtime))
    versions.sort(key=lambda item: -item[1])
    on_disk[suite] = [name for name, _ in versions]
    print(f"{suite}: {on_disk[suite]}")

print()

# 2) pilot gates present
print("== pilot gates ==")
gates = {}
for suite in ORDER:
    gate = ROOT / "artifacts" / "gates" / f"{suite}_B5_PILOT.json"
    if gate.is_file():
        g = json.loads(gate.read_text(encoding="utf-8"))
        gates[suite] = g
        print(f"{suite}: pass={g.get('pass')} run={g.get('run_id')}")
    else:
        print(f"{suite}: no gate")
print()

# 3) campaign state
s = json.loads((ROOT / "artifacts/gates/ONLINE_CAMPAIGN_STATE.json").read_text(encoding="utf-8"))
print("== campaign state ==")
print("formal complete:", [suite for suite, e in s["suites"].items() if e.get("formal_complete")])
print("campaign_complete:", s.get("campaign_complete"))
for suite in ORDER:
    e = s["suites"].get(suite, {})
    if e:
        print(f"{suite} | formal_complete={e.get('formal_complete')} blocked={e.get('blocked')} run={e.get('formal_run_id')}")
print()

# 4) formal run dirs on disk with terminal counts
print("== formal run dirs ==")
for suite in ORDER:
    run_base = ROOT / "data" / "runs"
    if not run_base.is_dir():
        break
    for entry in sorted(run_base.glob(f"deepseek-v4.1-flash-{suite}-*-formal"), key=lambda p: -p.stat().st_mtime):
        results = entry / "results.json"
        if results.is_file():
            r = json.loads(results.read_text(encoding="utf-8"))
            terminal = sum(1 for v in r.values() if v.get("status") in {"COMPLETED", "INVALID_MODEL_OUTPUT"})
            print(f"{suite}: {entry.name} | {len(r)} units | {terminal} terminal")
        else:
            print(f"{suite}: {entry.name} | no results.json")
