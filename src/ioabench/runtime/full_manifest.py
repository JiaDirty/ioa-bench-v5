"""Build and freeze the component-pinned manifest for a benchmark run."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from ioabench.contracts import assert_valid, load_document
from ioabench.hashing import canonical_sha256
from .manifest import ImmutableManifestStore


class FullRunManifest:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.schema = load_document(self.root / "contracts" / "schema" / "run_manifest.schema.json")

    def build(self, *, run_id: str, model_id: str, dataset_pack: str = "v1", parameters: Mapping[str, Any] | None = None, runtime_metadata: Mapping[str, Any] | None = None,
              release: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not run_id or not model_id:
            raise ValueError("run_id and model_id are required")
        pack_path = _dataset_pack_path(self.root, dataset_pack)
        pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
        suites = dict(pack.get("suites", {}))
        if len(suites) != 18:
            raise ValueError("dataset pack must pin all 18 suites")
        dataset_versions: dict[str, str] = {}
        dataset_hashes: dict[str, str] = {}
        for suite, item in suites.items():
            version = str(item["version"])
            dataset_manifest_path = self.root / "data" / "datasets" / suite / version / "manifest.json"
            if not dataset_manifest_path.exists():
                raise FileNotFoundError(dataset_manifest_path)
            dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
            # Dataset manifests identify their suite as either `test_id` (T311
            # generation lineage) or `suite_id` (all other suites); both are the
            # same identity and must agree with the pack pin.
            declared_suite = dataset_manifest.get("test_id", dataset_manifest.get("suite_id"))
            if declared_suite != suite or dataset_manifest.get("version") != version:
                raise ValueError(f"dataset manifest does not match pack pin: {suite}@{version}")
            if dataset_manifest.get("content_sha256") != item.get("content_sha256"):
                raise ValueError(f"dataset hash does not match pack pin: {suite}@{version}")
            cases_path = dataset_manifest_path.parent / "cases.jsonl"
            cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line]
            if canonical_sha256({"manifest": {**dataset_manifest, "content_sha256": None}, "cases": cases}) != dataset_manifest.get("content_sha256"):
                raise ValueError(f"dataset content hash is invalid: {suite}@{version}")
            dataset_versions[suite] = version
            dataset_hashes[suite] = str(dataset_manifest["content_sha256"])
        manifest: dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": run_id,
            "profile": "local-v1",
            "tested_model": {"provider": "aihubmix", "model_id": model_id, "parameters": dict(parameters or {})},
            "benchmark": {
                "suite_versions": dict(dataset_versions),
                "dataset_versions": dict(dataset_versions),
                "dataset_hashes": dict(dataset_hashes),
                "scorer_versions": {suite: "v1" for suite in suites},
                "base_prompt_versions": {suite: "neutral-v1" for suite in suites},
                "dataset_pack": f"DATASET_PACK_{dataset_pack.upper()}",
            },
            "runtime": {
                "git_sha": _git_sha(self.root),
                "dependency_lock_sha256": _dependency_hash(self.root),
                "os": platform.platform(),
                "python_version": platform.python_version(),
                **dict(runtime_metadata or {}),
            },
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        }
        if release is not None:
            manifest["release"] = {
                "release_id": release["release_id"],
                "release_sha256": release["release_sha256"],
                "source_tree_sha256": release["source_tree_sha256"],
                "dataset_pack_v4_sha256": release.get("dataset_pack_v4_sha256"),
                "strict_retry_semantics": release.get("strict_retry_semantics"),
            }
        assert_valid(manifest, self.schema)
        return manifest

    def freeze(self, manifest: Mapping[str, Any], output_root: str | Path | None = None) -> Path:
        target_root = Path(output_root) if output_root is not None else self.root / "data" / "runs" / "manifests"
        return ImmutableManifestStore(target_root).freeze(manifest)


def _dependency_hash(root: Path) -> str:
    path = root / "pyproject.toml"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else canonical_sha256({})


def _git_sha(root: Path) -> str:
    head = root / ".git" / "HEAD"
    if head.exists():
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref: "):
            reference = root / ".git" / value[5:]
            if reference.exists():
                return reference.read_text(encoding="utf-8").strip()
        else:
            return value
    return "sha256:" + source_tree_hash(root)


def source_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for directory in ("src", "contracts", "config"):
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _dataset_pack_path(root: Path, dataset_pack: str) -> Path:
    candidates = (
        root / "data" / "datasets" / f"DATASET_PACK_{dataset_pack}.yaml",
        root / "data" / "datasets" / f"DATASET_PACK_{dataset_pack.upper()}.yaml",
        root / "data" / "datasets" / f"DATASET_PACK_{dataset_pack.lower()}.yaml",
    )
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(candidates[0])
