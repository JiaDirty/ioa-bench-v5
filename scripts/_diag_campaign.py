"""Diagnose T323 instant-rejection anomaly and current campaign state."""
import json
import os
import time
import glob
from pathlib import Path
from collections import Counter

ROOT = Path(".")

s = json.loads((ROOT / "artifacts/gates/ONLINE_CAMPAIGN_STATE.json").read_text(encoding="utf-8"))
print("formal complete:", [suite for suite, e in s["suites"].items() if e.get("formal_complete")])
print("campaign_complete:", s.get("campaign_complete"))
print()

# T323 state entry and pilot dirs
e = s["suites"].get("T323", {})
print("T323 state entry:")
print("  pilot:", json.dumps(e.get("pilot", {}), ensure_ascii=False)[:300])
print("  formal_complete:", e.get("formal_complete"), "| blocked:", e.get("blocked"))
print()

runs = sorted(glob.glob("data/runs/T323-pilot-*"), key=os.path.getmtime)
print("all T323 pilot runs (newest last):")
for run in runs[-4:]:
    age = round((time.time() - Path(run).stat().st_mtime) / 60, 1)
    report = Path(run) / "pilot-report.json"
    has_report = report.is_file()
    print(f"  {Path(run).name} | age {age} min | report: {has_report}")
    if has_report:
        r = json.loads(report.read_text(encoding="utf-8"))
        print(f"    pass={r['pilot_pass']} dataset={r.get('dataset_version')}")
        sem = r.get("semantic_validation") or {}
        print(f"    semantic: {sem.get('accepted_cases')}/{sem.get('total_cases')}")

# T323 2.3.0 dataset sanity: cases count, unique IDs, narrative fields
p = ROOT / "data/datasets/T323/2.3.0/cases.jsonl"
cases = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
unique = len({c["candidate_id"] for c in cases})
print(f"\nT323@2.3.0 dataset: {len(cases)} cases, {unique} unique IDs")
case = cases[0]
for key in ("task", "stimulus", "stimulus_detail"):
    print(f"  {key}: {str(case['sut_payload'].get(key))[:110]}")

# stamp/cache existence right now
for f in ("semantic-validation.json", "semantic-validation-cache.json"):
    fp = ROOT / f"data/datasets/T323/2.3.0/{f}"
    print(f"T323 2.3.0 {f}: {'EXISTS age ' + str(round((time.time() - fp.stat().st_mtime)/60, 1)) + ' min' if fp.is_file() else 'absent'}")

# T331 pilot progress
runs = sorted(glob.glob("data/runs/T331-pilot-*"), key=os.path.getmtime)
run_dir = Path(runs[-1])
report = run_dir / "pilot-report.json"
print(f"\nnewest T331 pilot: {run_dir.name} | dir age: {round((time.time() - run_dir.stat().st_mtime)/60, 1)} min")
if report.is_file():
    r = json.loads(report.read_text(encoding="utf-8"))
    print("  T331 pilot DONE | pass:", r["pilot_pass"], "| dataset:", r.get("dataset_version"))
    for k, v in r["checks"].items():
        if not v["pass"]:
            print("   FAIL", k, ":", json.dumps(v["evidence"])[:250])
    sem = r.get("semantic_validation") or {}
    print("  semantic:", sem.get("accepted_cases"), "/", sem.get("total_cases"))
    statuses = Counter(x["status"] for x in r["executions"].values())
    print("  executions:", dict(statuses))
else:
    print("  still executing")

# formal runs
for suite, ver in (("T331", "2.4.0"), ("T332", "2.3.0"), ("T333", "2.4.0")):
    cp = ROOT / f"data/runs/deepseek-v4.1-flash-{suite}-{ver}-formal/checkpoint.json"
    if cp.is_file():
        state = json.loads(cp.read_text(encoding="utf-8"))
        print(f"{suite} formal: {len(state)} units | {dict(Counter(v.get('status') for v in state.values()))} | age: {round(time.time() - os.path.getmtime(cp), 1)} s")
