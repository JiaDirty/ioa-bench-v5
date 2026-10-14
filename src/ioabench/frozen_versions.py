"""Authoritative frozen dataset versions for the 18 suites (single source of truth).

Every consumer (campaign driver, pilot script, dispatcher test, reconciler,
run classifier, pack/release builders, independent validation) MUST import
this map instead of embedding its own copy.  The T323 map-omission incident
(2026-09-29) and the T351 version drift showed that duplicated literal maps
silently diverge; this module makes one map load-bearing.
"""
from __future__ import annotations

import json
from pathlib import Path

FROZEN_VERSIONS: dict[str, str] = {
    "T311": "2.0.0", "T312": "2.2.0", "T313": "2.3.0", "T321": "2.2.0",
    "T322": "2.4.0", "T323": "2.4.0", "T331": "2.4.0", "T332": "2.3.0",
    "T333": "2.4.0", "T341": "2.4.0", "T342": "2.4.0", "T343": "2.4.0",
    "T351": "2.3.0", "T352": "2.2.0", "T353": "2.3.0", "T361": "2.3.0",
    "T362": "2.4.0", "T363": "2.3.0"}

SUITES: tuple[str, ...] = ("T311", "T312", "T313", "T321", "T322", "T323", "T331",
                           "T332", "T333", "T341", "T342", "T343", "T351", "T352",
                           "T353", "T361", "T362", "T363")

SIMULATION_SUITES: frozenset[str] = frozenset({"T361", "T362", "T363"})


def dataset_dir(root: str | Path, suite: str) -> Path:
    return Path(root) / "data" / "datasets" / suite / FROZEN_VERSIONS[suite]


def assert_frozen_on_disk(root: str | Path) -> None:
    """Refuse silent legacy fallbacks: every mapped suite must exist frozen."""
    missing = [suite for suite in SUITES if not (dataset_dir(root, suite) / "cases.jsonl").is_file()]
    if missing:
        raise FileNotFoundError(f"frozen datasets missing on disk for: {missing}")


def manifest_for(root: str | Path, suite: str) -> dict:
    return json.loads((dataset_dir(root, suite) / "manifest.json").read_text(encoding="utf-8"))
