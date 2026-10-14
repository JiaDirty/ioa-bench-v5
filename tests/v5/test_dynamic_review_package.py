"""Supplied dynamic cases produce blinded engineering review material without provider calls."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

from ioabench.v5.dynamic import t321_slice
from ioabench.v5.evaluation import execute_case
from ioabench.v5.gates import PROFILE

ROOT = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("dynamic_review_package", ROOT / "scripts/v5/build_review_package.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _cases(tmp_path):
    control, risk = t321_slice.generate(seed=5, families=1)[0]
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(c.as_dict(), ensure_ascii=False) + "\n" for c in (control, risk)), encoding="utf-8")
    return path, control, risk


def _forbidden_keys(value):
    forbidden = {"arm", "oracle", "model_id", "score", "scorer_safety", "scorer_utility", "case_id", "structure_id"}
    if isinstance(value, dict):
        return (set(value) & forbidden) | set().union(*(_forbidden_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_forbidden_keys(v) for v in value))
    return set()


def test_part_b_executes_supplied_dynamic_pair_and_records_sample_shortfalls(tmp_path):
    tool = _tool()
    path, control, risk = _cases(tmp_path)
    sealed = []
    sampling = asyncio.run(tool.part_b(tmp_path, 20261012, None, sealed, cases_path=path))
    items = [json.loads(line) for line in (tmp_path / "part_b_items.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(items) == 2 and {item["suite"] for item in items} == {"T321"}
    assert all(not _forbidden_keys(item) for item in items)
    assert {item["structure_id"] for item in sealed} == {"T321-DYNA"}
    assert {item["case_sha256"] for item in sealed} == {control.content_sha256(), risk.content_sha256()}
    assert sampling["T321"]["cases"] == 2 and sampling["T321"]["shortfall_cases"] == 10
    assert sampling["T321"]["strata"]["M"]["shortfall_pairs"] == 2
    assert sampling["T311"]["shortfall_cases"] == 12


def test_supplied_input_reuses_pair_and_identifier_validation(tmp_path):
    tool = _tool()
    path, control, _ = _cases(tmp_path)
    path.write_text(json.dumps(control.as_dict()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete supplied pair"):
        tool._supplied_pairs(path)
    bad = control.as_dict()
    bad["case_id"] = "../unsafe"
    path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe run/case identifier"):
        tool._supplied_pairs(path)


def test_part_c_canonicalizes_dynamic_results_and_excludes_latest_ineligible_attempt(tmp_path):
    tool = _tool()
    _, control, risk = _cases(tmp_path)
    result = execute_case(tmp_path, control, t321_slice.policies()["witness"], PROFILE, "review-fixture", {})
    invalid = deepcopy(result)
    invalid.update(case_id=risk.case_id, scientifically_eligible=False)
    invalid["attempt_no"] = 2
    original = deepcopy(invalid)
    original.update(attempt_no=1, scientifically_eligible=True)
    source = tmp_path / "results.jsonl"
    source.write_text("".join(json.dumps(r) + "\n" for r in (result, original, invalid)), encoding="utf-8")
    sealed = []
    tool.part_c(tmp_path, 5, [source], sealed, "reference-policy")
    items = [json.loads(line) for line in (tmp_path / "part_c_items.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(items) == 1 and items[0]["suite"] == "T321"
    assert not _forbidden_keys(items[0])
    assert sealed[0]["structure_id"] == "T321-DYNA"
    assert sealed[0]["case_id"] == control.case_id


def test_cli_supplied_case_package_pins_source_and_remains_materials_only(tmp_path, monkeypatch):
    tool = _tool()
    cases_path, control, _ = _cases(tmp_path)
    result = execute_case(tmp_path, control, t321_slice.policies()["witness"], PROFILE, "review-cli-fixture", {})
    source = tmp_path / "results.jsonl"
    source.write_text(json.dumps(result) + "\n", encoding="utf-8")
    package = tmp_path / "review"
    monkeypatch.setattr(sys, "argv", ["build_review_package.py", "--cases", str(cases_path),
                                     "--results", str(source), "--model-id", "reference-policy", "--out", str(package)])
    tool.main()
    manifest = json.loads((package / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["supplied_cases_source"]["sha256"] == hashlib.sha256(cases_path.read_bytes()).hexdigest()
    assert manifest["results_source_hashes"][str(source)] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["schema_version"].endswith("/4")
    assert manifest["package_scope"] == "ENGINEERING_SUPPLIED_CASES"
    assert manifest["gate_d_confirmatory_ready"] is False
    assert manifest["sample_shortfalls"]["T321"]["part_b"]["shortfall_cases"] == 10
    assert manifest["sample_shortfalls"]["T311"]["part_c"]["shortfall_items"] == 15
    with zipfile.ZipFile(package / "reviewer_materials.zip") as archive:
        assert archive.testzip() is None
        assert "sealed_key.jsonl" not in archive.namelist() and "MANIFEST.json" not in archive.namelist()
        public_manifest = json.loads(archive.read("REVIEWER_MANIFEST.json"))
        assert public_manifest["package_scope"] == "ENGINEERING_SUPPLIED_CASES"
        assert public_manifest["sample_shortfalls"]["T321"]["part_b"]["shortfall_cases"] == 10
    before = (package / "MANIFEST.json").read_bytes()
    with pytest.raises(SystemExit):
        tool.main()
    assert (package / "MANIFEST.json").read_bytes() == before


def test_abstention_enters_blind_review_without_becoming_a_safe_label(tmp_path):
    tool = _tool()
    _, control, _ = _cases(tmp_path)
    row = execute_case(tmp_path, control, t321_slice.policies()["witness"], PROFILE, "review-abstain", {})
    row["outcome"]["eligibility"] = "SCORER_ABSTAINED"
    row["scientifically_eligible"] = False
    row["score"]["abstain"] = True
    invalid = deepcopy(row)
    invalid["case_id"] = "broken-ledger"
    invalid["monitor_report"]["ledger_integrity"]["passed"] = False
    source = tmp_path / "results.jsonl"
    source.write_text("".join(json.dumps(r) + "\n" for r in (row, invalid)), encoding="utf-8")
    sealed = []
    tool.part_c(tmp_path, 5, [source], sealed, "reference-policy", include_abstained=True)
    items = [json.loads(s) for s in (tmp_path / "part_c_items.jsonl").read_text().splitlines()]
    assert len(items) == 1 and not _forbidden_keys(items[0])
    assert sealed[0]["scorer_safety"] is None
    assert sealed[0]["scorer_eligibility"] == "SCORER_ABSTAINED"


def test_visible_review_transcript_keeps_tool_contracts_without_private_reasoning():
    tool = _tool()
    records = [{"agent_id": "a", "request": {"tools": [{"function": {"name": "send", "description": "Full record attachments"}}],
                "messages": [{"role": "assistant", "content": "Visible text", "reasoning_content": "private reasoning"}]},
                "response": {"text": "Done", "reasoning_content": "private final reasoning"}}]
    before = deepcopy(records)
    rendered = tool._transcript(records)
    assert rendered[0]["tool_schemas"][0]["function"]["description"] == "Full record attachments"
    assert "private reasoning" not in json.dumps(rendered)
    assert "private final reasoning" not in json.dumps(rendered)
    assert records == before


def test_part_b_uses_required_candidate_profile(tmp_path, monkeypatch):
    from dataclasses import replace
    from ioabench.v5.suites import t361
    from ioabench.v5.scenario_profiles import PROFILE_ID, scenario_for
    tool = _tool()
    pair = [replace(case, provenance={**case.provenance, "required_scenario_profile": PROFILE_ID})
            for case in t361.generate(7, families=1)[0]]
    path = tmp_path / "authored.jsonl"
    path.write_text("".join(json.dumps(c.as_dict()) + "\n" for c in pair), encoding="utf-8")
    monkeypatch.setattr(tool, "implemented", lambda: ("T361",))
    asyncio.run(tool.part_b(tmp_path, 5, None, [], cases_path=path))
    items = [json.loads(s) for s in (tmp_path / "part_b_items.jsonl").read_text().splitlines()]
    expected = scenario_for(pair[0]).agents(pair[0].world)[0].system_prompt
    assert items[0]["visible_material"][0]["messages"][0]["content"] == expected
