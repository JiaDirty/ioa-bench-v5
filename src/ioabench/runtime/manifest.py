"""Immutable run-manifest persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256


class ImmutableManifestStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def freeze(self, manifest: Mapping[str, Any]) -> Path:
        run_id = str(manifest["run_id"])
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{run_id}.json"
        if target.exists():
            raise FileExistsError(f"run manifest is already frozen: {run_id}")
        payload = dict(manifest)
        payload.setdefault("manifest_sha256", canonical_sha256(manifest))
        target.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return target

    def load(self, run_id: str) -> dict[str, Any]:
        value = json.loads((self.root / f"{run_id}.json").read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("run manifest must be an object")
        return value
