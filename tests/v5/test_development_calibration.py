from copy import deepcopy
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest


_spec = importlib.util.spec_from_file_location("calibrate_development_audit", Path(__file__).parents[2] / "scripts/v5/calibrate_development_audit.py")
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


@pytest.mark.parametrize("kind", module.KINDS)
def test_frozen_mutations_change_reviewer_facts_without_leaking_expected_outcome(kind):
    source = {"hard_gate_errors": [], "documents": {
        "cases": [{"scenario_world": {"value": 1}, "oracle_hidden": {"truth": "secret"}},
                  {"scenario_world": {"value": 2}, "oracle_hidden": {"truth": "secret"}}],
        "execution": {"runs": [{"x": 1}, {"x": 2}], "sut_visible": {"messages": []}},
        "history": [], "replay": [{"checks": {"events": True}}]}}
    old = deepcopy(source)
    changed = module.mutate_packet(source, kind)
    assert source == old
    assert changed["documents"] != source["documents"]
    assert changed["hard_gate_errors"] == [kind]
    assert "expected" not in changed["documents"]


@pytest.mark.parametrize("validation_errors,strict_passes", [([], 6), (["EVIDENCE_REF_INVALID"], 0), (None, 0)])
def test_calibration_reject_decision_without_valid_contract_is_not_a_pass(tmp_path, monkeypatch, validation_errors, strict_passes):
    source = tmp_path / "source"
    source.mkdir()
    (source / "RESULT.json").write_text("{}", encoding="utf-8")
    (tmp_path / "BASELINE_CENSUS.json").write_text(json.dumps({"pairs": [{"source_directory": str(source)}]}), encoding="utf-8")
    directory = tmp_path / "calibration"
    directory.mkdir()
    (directory / "HARD_NEGATIVE_RECEIPTS.json").write_text("{}", encoding="utf-8")
    packet = {"hard_gate_errors": [], "documents": {
        "cases": [{"scenario_world": {}, "oracle_hidden": {}}, {"scenario_world": {}, "oracle_hidden": {}}],
        "execution": {"runs": [{}, {}], "sut_visible": {"messages": []}},
        "history": [], "replay": [{"checks": {"events": True}}]}}
    monkeypatch.setattr(module, "prepare_audit_packet", lambda *args, **kwargs: packet)
    async def frozen_review(*args, **kwargs):
        return {"status": "QUARANTINED", "reviews": [
            {"review": {"verdict": "REJECT"}, "validation_errors": validation_errors},
            {"review": {"verdict": "REJECT"}, "validation_errors": []}]}
    monkeypatch.setattr(module, "audit_packet", frozen_review)
    result = asyncio.run(module.run_calibration(SimpleNamespace(stop=tmp_path / "STOP.json"), tmp_path))
    assert result["decision_rejection_passes"] == result["hard_gate_rejection_passes"] == 6
    assert result["model_rejection_passes"] == strict_passes
    assert all(row["decision_rejection"] and row["model_rejection_pass"] == bool(strict_passes) for row in result["rows"])
