from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import yaml

from ioabench.hashing import canonical_sha256

SUITES = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333", "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")


def load_formal(root: Path, suite: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pack = yaml.safe_load((root / "data" / "datasets" / "DATASET_PACK_v1.yaml").read_text(encoding="utf-8"))
    dataset = root / "data" / "datasets" / suite / str(pack["suites"][suite]["version"])
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    return manifest, cases


def content_hash(manifest: dict[str, Any], cases: list[dict[str, Any]]) -> str:
    return canonical_sha256({"manifest": {**manifest, "content_sha256": None}, "cases": cases})


def expose_case(suite: str, case: dict[str, Any]) -> bool:
    generation = import_module(f"ioabench.suites.{suite.lower()}.generation")
    scenario_module = import_module(f"ioabench.suites.{suite.lower()}.scenario")
    generator = getattr(generation, f"{suite}Generator")
    scenario_cls = getattr(scenario_module, f"{suite}Scenario")
    controller_cls = getattr(scenario_module, f"{suite}ExposureController")
    scenario = scenario_cls(f"{suite.lower()}-formal-preflight", "1.0.0", generator().generate(seed=case["provenance"]["seed"]), ())
    controller = controller_cls()
    controller.expose(scenario, lambda payload: payload)
    return controller.exposure_proven()
