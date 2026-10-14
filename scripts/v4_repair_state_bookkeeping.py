"""Repair stale work-queue bookkeeping left by the v3.2 sync.

The v3.2 sync advanced WORK_QUEUE.yaml (version 17, 441 items) but left the
canonical state/WORK_QUEUE_VALIDATION.json at an older generation (428 items,
version 8) and omitted summary.task_count, so the repository's own
state-consistency test fails. This restores internal consistency; it does not
change any scientific artifact, gate, run, dataset or release.
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path("D:/Project/ioa_codex_spec")
QUEUE = ROOT / "state/WORK_QUEUE.yaml"
STATE = ROOT / "state/PROJECT_STATE.yaml"
VALIDATION = ROOT / "state/WORK_QUEUE_VALIDATION.json"

queue = yaml.safe_load(QUEUE.read_text(encoding="utf-8"))
state = yaml.safe_load(STATE.read_text(encoding="utf-8"))
validation = json.loads(VALIDATION.read_text(encoding="utf-8"))

items = queue["items"]
validation.update({
    "work_queue_version": queue.get("version"),
    "task_count": len(items),
    "milestone_counts": dict(sorted(Counter(str(i.get("milestone")) for i in items).items())),
    "status_counts": dict(sorted(Counter(str(i.get("status")) for i in items).items())),
    "repaired_by": "scripts/v4_repair_state_bookkeeping.py",
    "note": "counts recomputed from state/WORK_QUEUE.yaml; superseded generations preserved in WORK_QUEUE_VALIDATION_v*_001.json",
})
VALIDATION.write_text(json.dumps(validation, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

queue.setdefault("summary", {})["task_count"] = len(items)
queue["summary"]["version"] = queue.get("version")
QUEUE.write_text(yaml.safe_dump(queue, allow_unicode=True, sort_keys=False), encoding="utf-8")

state["work_queue_task_count"] = len(items)
state["work_queue_version"] = queue.get("version")
STATE.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

print(json.dumps({"queue_version": queue.get("version"), "task_count": len(items),
                  "validation_version": validation["work_queue_version"]}))
