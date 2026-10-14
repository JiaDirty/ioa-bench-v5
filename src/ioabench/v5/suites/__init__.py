"""Registry of v5 suite modules.

Each module exposes: SUITE_ID, SCENARIO_VERSION, SCORER_VERSION, GENERATOR_VERSION, a ``<SUITE>Scenario``
class, ``score(trace, case)``, ``policies()``, ``EXPECTED_REFERENCE`` and ``generate(seed, families)``.
Optional: ``reference_auxiliary()`` returning auxiliary actors (e.g. a scripted persona) for offline runs.
"""
from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType
from typing import Any

SUITE_MODULES: dict[str, str] = {suite: f"ioabench.v5.suites.{suite.lower()}" for suite in (
    "T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
    "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")}


def implemented() -> list[str]:
    """Suites whose module exists on disk (all 18 are registered; implementation is incremental)."""
    return [suite for suite, name in SUITE_MODULES.items() if importlib.util.find_spec(name) is not None]


def load(suite_id: str) -> ModuleType:
    if suite_id not in SUITE_MODULES:
        raise KeyError(f"unknown suite {suite_id}")
    return importlib.import_module(SUITE_MODULES[suite_id])


def scenario(suite_id: str) -> Any:
    return getattr(load(suite_id), f"{suite_id}Scenario")()
