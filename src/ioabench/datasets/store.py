"""Immutable, content-addressed dataset manifest and case storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ioabench.contracts import assert_valid, load_document
from ioabench.hashing import canonical_sha256


class DatasetStore:
    def __init__(self, root: str | Path, schema_path: str | Path | None = None) -> None:
        self.root = Path(root)
        self.schema_path = Path(schema_path) if schema_path else Path(__file__).resolve().parents[3] / "contracts" / "schema" / "dataset.schema.json"

    def freeze(self, manifest: Mapping[str, Any], cases: Iterable[Mapping[str, Any]], rejected: Iterable[Mapping[str, Any]] = ()) -> Path:
        payload = dict(manifest)
        if payload.get("status") != "FROZEN":
            raise ValueError("only FROZEN datasets may be persisted")
        case_list = [dict(case) for case in cases]
        payload["content_sha256"] = None
        assert_valid(payload, load_document(self.schema_path))
        content_sha256 = canonical_sha256({"manifest": payload, "cases": case_list})
        payload["content_sha256"] = content_sha256
        target = self.root / str(payload["dataset_id"]) / str(payload["version"])
        if target.exists():
            raise FileExistsError(f"dataset version already frozen: {payload['dataset_id']}@{payload['version']}")
        target.mkdir(parents=True, exist_ok=False)
        (target / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (target / "cases.jsonl").write_text("".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in case_list), encoding="utf-8")
        rejected_list = [dict(item) for item in rejected]
        (target / "rejected.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rejected_list), encoding="utf-8")
        return target

    def load_manifest(self, dataset_id: str, version: str) -> dict[str, Any]:
        return json.loads((self.root / dataset_id / version / "manifest.json").read_text(encoding="utf-8"))
