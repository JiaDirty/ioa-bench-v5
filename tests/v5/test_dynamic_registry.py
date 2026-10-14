"""Persisted dynamic cases use an exact opt-in registry without widening classic loading."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from ioabench.v5.core.case import CaseError, case_from_dict, validate_case
from ioabench.v5.dynamic.registry import get_adapter, implemented, load_case
from ioabench.v5.suites import load


@pytest.mark.parametrize("suite_id", implemented())
def test_all_dynamic_cases_roundtrip_without_changing_content_hash(suite_id):
    adapter = get_adapter(suite_id)
    assert adapter.SLICE_ID == suite_id
    for case in adapter.generate(seed=5, families=1)[0]:
        raw = json.loads(json.dumps(case.as_dict()))
        with pytest.raises(CaseError, match="unknown suite"):
            case_from_dict(raw)
        restored = load_case(raw)
        assert restored.content_sha256() == case.content_sha256()
        assert restored.as_dict() == raw
        assert restored.simulation_only == (suite_id in {"T361-DYNA", "T362-DYNA", "T363-DYNA"})
        validate_case(restored, allow_dynamic=True)
        with pytest.raises(CaseError, match="unknown suite"):
            validate_case(restored)


def test_registry_covers_18_constructs_and_19_exact_adapters():
    assert len(implemented()) == 19
    assert {suite_id.split("-")[0] for suite_id in implemented()} == {
        "T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
        "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363"}


@pytest.mark.parametrize("suite_id", ["T321-DYNC", "T361-DYNA-extra", "T321", "unknown"])
def test_unknown_or_classic_ids_cannot_select_dynamic_adapter(suite_id):
    with pytest.raises(KeyError, match="unknown dynamic suite"):
        get_adapter(suite_id)
    raw = get_adapter("T321-DYNA").generate(seed=5, families=1)[0][0].as_dict()
    raw["suite_id"] = suite_id
    with pytest.raises(CaseError, match="unknown dynamic suite"):
        load_case(raw)
    if suite_id != "T321":
        with pytest.raises(CaseError, match="unknown suite"):
            case_from_dict(raw, allow_dynamic=True)


@pytest.mark.parametrize("field,value", [("arm", "OTHER"), ("difficulty", "X"),
                                        ("mechanism_slots", []), ("mechanism_slots", ["/missing"]),
                                        ("fingerprints", []), ("fingerprints", ["x"]),
                                        ("schema_version", "other")])
def test_dynamic_loading_retains_core_schema_and_invariant_checks(field, value):
    raw = get_adapter("T321-DYNA").generate(seed=5, families=1)[0][0].as_dict()
    raw[field] = value
    with pytest.raises(CaseError):
        load_case(raw)


@pytest.mark.parametrize("suite_id", ["T311", "T361", "T362", "T363"])
def test_classic_loading_and_simulation_flags_stay_unchanged(suite_id):
    case = load(suite_id).generate(seed=5, families=1)[0][0]
    restored = case_from_dict(json.loads(json.dumps(case.as_dict())))
    assert restored.content_sha256() == case.content_sha256()
    assert restored.simulation_only == (suite_id != "T311")
    spoofed = replace(case, suite_id=f"{suite_id}-unregistered", provenance={"simulation_only": True})
    assert not spoofed.simulation_only


def test_adapter_module_identity_is_checked(monkeypatch):
    adapter = get_adapter("T321-DYNA")
    monkeypatch.setattr(adapter, "SLICE_ID", "T321-DYNB")
    with pytest.raises(ValueError, match="identity mismatch"):
        get_adapter("T321-DYNA")
