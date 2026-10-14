"""Deterministic representative-case selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def select_cases(root: str | Path, run_id: str, limit: int = 3) -> list[dict[str, Any]]:
    root = Path(root)
    records = json.loads((root / "data" / "runs" / run_id / "results.json").read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = []
    for status in ("UNSAFE_ACTION", "LATE_RECOVERY", "EARLY_SAFE", "TASK_SAFE_BUT_FAILED"):
        candidates = sorted((record for record in records.values() if record.get("score", {}).get("outcome_class") == status), key=lambda item: (item.get("suite", ""), item.get("case_id", "")))
        if candidates:
            selected.append({"kind": status, "suite": candidates[0].get("suite"), "case_id": candidates[0].get("case_id"), "replay": candidates[0].get("replay"), "replay_sha256": candidates[0].get("replay_sha256")})
        if len(selected) >= limit:
            break
    return selected


def write_case_selection(root: str | Path, run_id: str) -> Path:
    path = Path(root) / "data" / "reports" / run_id / "case-studies" / "selected.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(select_cases(root, run_id), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
