"""Build the round EVIDENCE_INDEX.json mapping every deliverable to its artifact."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
EXPORT = ROOT / "exports/tree-factory-handoff-20261024"

FILES = {
    "baseline": ["BASELINE.json", "PROTECTED_HISTORY_MANIFEST.json", "SOURCE_DEPENDENCY_MAP.md"],
    "audit_facts_M1": ["P0_AUDIT_AND_WITNESS_REPORT.md", "AUDIT_CALIBRATION.json"],
    "tree_M2": ["TREE_SPEC.json", "TREE_SELECTION_RECEIPTS.jsonl", "TREE_COVERAGE.json"],
    "ir_M3": ["MECHANISM_IR_SCHEMA.json", "COMPILER_CAPABILITIES.json", "ASSERTION_WITNESSES.jsonl", "M3_SUMMARY.json"],
    "online_M4": ["LIVE_MODEL_CONTRACT.json", "T331_MINIMAL_ONLINE.json", "MODEL_CATALOG.json",
                  "STOP_RESOLUTION.json", "STOP_RESOLUTION_2.json", "REQUEST_LEDGER.jsonl"],
    "ab_M5": ["TASK_SET_FROZEN.json", "AB_PREREGISTRATION.json", "ab/AB_RESULTS.csv",
              "ab/COST_AND_YIELD.json", "ab/FAILURE_FUNNEL.csv", "ab/RUN_SUMMARY.json"],
    "expansion_M6": ["SUITE18_CAPABILITY_READINESS.csv", "DIMENSION_REVIEW_PROPOSAL.md",
                     "T322_VERSION_SCOPED_PLAN.md"],
    "closeout_M7": ["FULL_REGRESSION.xml", "M7_CLOSEOUT.json", "HISTORY_PROTECTION.json",
                    "SECRET_SCAN.json", "GOAL_PROGRESS.json", "ROUND_REPORT.md"],
    "handoff": ["../../exports/tree-factory-handoff-202624/HANDOFF_MANIFEST.json"],
}
index = {"version": "ioabench.v5.evidence-index/1.0.0", "run": "tf-20261024-r1",
         "sections": {}}
for section, names in FILES.items():
    if section == "handoff":
        rows = [{"file": (EXPORT / name).relative_to(ROOT).as_posix(),
                 "bytes": (EXPORT / name).stat().st_size,
                 "sha256": hashlib.sha256((EXPORT / name).read_bytes()).hexdigest()}
                for name in ("HANDOFF_MANIFEST.json", "HANDOFF_VERIFICATION.json")
                if (EXPORT / name).is_file()]
        index["sections"][section] = rows
        continue
    rows = []
    for name in names:
        path = RUN / name
        if not path.is_file():
            rows.append({"file": name, "status": "MISSING"})
            continue
        rows.append({"file": name, "bytes": path.stat().st_size,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    index["sections"][section] = rows
# candidate evidence pointer
minimal = RUN / "minimal/candidates/T331-minimal-online"
index["live_candidate"] = {
    "directory": "minimal/candidates/T331-minimal-online",
    "result": "RESULT.json (engineering PASS, audit QUARANTINED by REQUEST_UNRESOLVED)",
    "files": sorted(p.name for p in minimal.iterdir() if p.is_file())[:20]}
(RUN / "EVIDENCE_INDEX.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
print(json.dumps({"sections": {k: len(v) for k, v in index["sections"].items()}}))
