"""Atomic JSON checkpoints that survive process restarts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


class CheckpointStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def save(self, run_id: str, state: Mapping[str, Any]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{run_id}.json"
        temporary = self.root / f".{run_id}.{uuid4().hex}.tmp"
        temporary.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temporary.replace(target)
        return target

    def load(self, run_id: str) -> dict[str, Any] | None:
        target = self.root / f"{run_id}.json"
        if not target.exists():
            return None
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"checkpoint must be an object: {target}")
        return value
