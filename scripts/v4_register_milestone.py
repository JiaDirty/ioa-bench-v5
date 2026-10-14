"""Register the v4 milestone in the work queue's milestone map.

The v4 sync added the V4_CORRECTIVE_STRICT_CAMPAIGN milestone to the queue items
but not to the `milestones` map, so the repository state-consistency test fails.
This registers it with the same shape as the existing entries.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path("D:/Project/ioa_codex_spec")
QUEUE = ROOT / "state/WORK_QUEUE.yaml"
VALIDATION = ROOT / "state/WORK_QUEUE_VALIDATION.json"

queue = yaml.safe_load(QUEUE.read_text(encoding="utf-8"))
milestones = queue.get("milestones") or {}
sample = next(iter(milestones.values()))
if isinstance(sample, dict):
    template = dict(sample)
else:
    template = None

entry = template if template is not None else "v4 corrective release and strict formal campaign"
if isinstance(entry, dict):
    for key in list(entry):
        if key in {"id", "name", "title"}:
            entry[key] = "V4_CORRECTIVE_STRICT_CAMPAIGN"
        elif key in {"description", "summary", "objective"}:
            entry[key] = "v4 corrective release; strict retry semantics; 18-suite post-freeze formal campaign"
        elif isinstance(entry[key], list):
            entry[key] = []
        elif isinstance(entry[key], bool):
            entry[key] = False
milestones["V4_CORRECTIVE_STRICT_CAMPAIGN"] = entry
queue["milestones"] = milestones

items = queue["items"]
validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
validation["milestone_counts"] = dict(sorted(Counter(str(i.get("milestone")) for i in items).items()))
validation["task_count"] = len(items)
validation["work_queue_version"] = queue.get("version")
VALIDATION.write_text(json.dumps(validation, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

queue.setdefault("summary", {})["task_count"] = len(items)
queue["summary"]["version"] = queue.get("version")
QUEUE.write_text(yaml.safe_dump(queue, allow_unicode=True, sort_keys=False), encoding="utf-8")

print(json.dumps({"milestone_registered": True,
                  "milestones": len(milestones),
                  "milestone_counts_match": set(milestones) == set(validation["milestone_counts"])}))
