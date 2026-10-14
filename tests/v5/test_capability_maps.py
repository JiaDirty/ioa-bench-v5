"""M1 contract tests: the dynamic-world capability maps stay consistent with the
construct maps (untouched authority) and the live suite modules."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_capability_maps", ROOT / "scripts" / "v5" / "validate_capability_maps.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capability_maps_contract_is_consistent() -> None:
    failures = _validator().validate()
    assert not failures, failures


def test_capability_maps_covers_all_18_suites_with_shared_registry() -> None:
    module = _validator()
    contract = json.loads(module.CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == module.SCHEMA_VERSION
    assert set(contract["suites"]) == {f"T3{a}{b}" for a in range(1, 7) for b in range(1, 4)}
    assert len(contract["shared_components"]) >= 12
    # event ledger is the universal backbone component
    for suite_id, entry in contract["suites"].items():
        assert "event_ledger" in entry["capabilities"]["shared"], suite_id


def test_capability_maps_do_not_redefine_constructs() -> None:
    """The contract's mechanism text must be a resume/citation, never a new norm source:
    its subtype ids come verbatim from construct_maps.json (checked in validate()), and the
    contract must carry the authority note pointing at the construct map."""
    module = _validator()
    contract = json.loads(module.CONTRACT.read_text(encoding="utf-8"))
    assert "construct_maps.json remains the sole construct authority" in contract["authority_note"]
    for entry in contract["suites"].values():
        assert entry["construct_ref"]["classification"] in {
            "RETAIN_AND_HARDEN", "SUBSTANTIAL_REDESIGN", "REBUILD_OPERATIONALIZATION"}
