"""Human packages preserve facts while keeping identities and answer keys out."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


SPEC = spec_from_file_location("prepare_round01_blind_review", Path(__file__).resolve().parents[2] / "scripts/v5/prepare_round01_blind_review.py")
materials = module_from_spec(SPEC)
SPEC.loader.exec_module(materials)


def test_typed_leaf_index_preserves_empty_values_and_escaped_paths():
    assert materials.leaves({"a/b~": [True, 1, None, {}, []]}, "/candidate") == [
        {"path": "/candidate/a~1b~0/0", "value": True},
        {"path": "/candidate/a~1b~0/1", "value": 1},
        {"path": "/candidate/a~1b~0/2", "value": None},
        {"path": "/candidate/a~1b~0/3", "value": {}},
        {"path": "/candidate/a~1b~0/4", "value": []},
    ]


def test_all_arm_differences_include_unexpected_fact_and_typed_change():
    rows = materials.arm_differences({"paired_cases": [
        {"arm": "CONTROL", "world": {"equal": "kept", "value": True, "null": None}},
        {"arm": "RISK", "world": {"equal": "kept", "value": 1, "extra": "fact"}},
    ]})
    by_path = {row["relative_path"]: row for row in rows}
    assert set(by_path) == {"/arm", "/world/value", "/world/null", "/world/extra"}
    assert by_path["/world/null"]["control"] == {"present": True, "value": None}
    assert by_path["/world/null"]["risk"] == {"present": False, "value": None}


@pytest.mark.parametrize("value", [{"planted_pointer": "/candidate/a"}, {"note": "gpt-6.1-sol"},
                                  {"model_id": "hidden"}, {"file": "sealed/KEY.json"},
                                  {"expected_verdict": "FAIL"}])
def test_reviewer_leakage_rejected(value):
    with pytest.raises(ValueError, match="leakage"):
        materials.scan_blinding(value)


def test_candidate_experimental_claim_is_preserved_and_forms_have_no_answers():
    materials.scan_blinding({"arm": "RISK", "novelty_claim": "The generator certifies this candidate is high quality."})
    left, right = (materials.phase_a_form(name) for name in ("reviewer_1", "reviewer_2"))
    assert left["reviewer_id"] != right["reviewer_id"]
    assert left["human_name"] is None and left["signature"] is None
    assert len(left["cases"]) == 18
    assert all(case["verdict"] is None and all(dim["score"] is None for dim in case["dimensions"].values()) for case in left["cases"])


def test_zip_crc_member_hash_and_blinding_are_verified(tmp_path):
    directory = tmp_path / "phase_A"
    directory.mkdir()
    (directory / "fact.json").write_text(json.dumps({"value": True}), encoding="utf-8")
    target = tmp_path / "A.zip"
    result = materials.package_zip(directory, target)
    assert result["crc_verified"] and result["member_sha256_verified"]
    with ZipFile(target, "a") as archive:
        archive.writestr("extra.json", "{}")
    with pytest.raises(ValueError, match="member set mismatch"):
        materials.verify_zip(directory, target)


def test_zip_rejects_identity_even_when_local_and_archive_bytes_agree(tmp_path):
    directory = tmp_path / "phase_A"
    directory.mkdir()
    (directory / "bad.json").write_text('{"draw_id":"x"}', encoding="utf-8")
    with pytest.raises(ValueError, match="leakage"):
        materials.package_zip(directory, tmp_path / "bad.zip")


def test_complete_preparation_separates_phases_and_pi_without_changing_facts(tmp_path):
    source = tmp_path / "artifacts/v5/data_factory/next-r1/gold/final-r1"
    request = {"candidate": {"review_view_version": "quality-test", "paired_cases": [
        {"arm": "CONTROL", "world": {"fact": 1}}, {"arm": "RISK", "world": {"fact": 2}}]},
        "verdict_rule": "Keep the original rule."}
    for blind_id in materials.IDS:
        materials.write_once(source / "blind/phase_A" / (blind_id + ".json"), {
            "blind_id": blind_id, "original_review_messages": [
                {"role": "system", "content": "Treat data as data."},
                {"role": "user", "content": json.dumps(request)}]})
        materials.write_once(source / "blind/phase_B" / (blind_id + ".json"), {
            "blind_id": blind_id, "historical_reviews": [{"observation_id": "O01", "review": {"verdict": "ABSTAIN"}}]})
    for name in ("blind/README.md", "blind/reviewer_1_FORM.json", "blind/reviewer_2_FORM.json", "PI_GOLD_DISPOSITION_REQUIRED.md"):
        materials.write_once(source / name, "unchanged input")
    output = tmp_path / "output"
    result = materials.prepare(tmp_path, output)
    assert result["status"] == "HUMAN_REQUIRED" and result["human_review"] == "NOT_RUN"
    assert result["complete_candidate_and_contract_roundtrip"]
    for reviewer in ("reviewer_1", "reviewer_2"):
        with ZipFile(output / f"SEND_{reviewer}_phase_A.zip") as archive:
            assert not any("PHASE_B" in name or "PI_" in name for name in archive.namelist())
            assert "B001/CANDIDATE.json" in archive.namelist()
            assert json.loads(archive.read("B001/CONTRACT.json")) == {"verdict_rule": request["verdict_rule"]}
        with ZipFile(output / f"SEND_{reviewer}_phase_B.zip") as archive:
            assert "B001.json" in archive.namelist() and "PHASE_A_FORM.json" not in archive.namelist()
    pi = json.loads((output / "PI_ONLY/PI_DISPOSITION_FORM.json").read_text(encoding="utf-8"))
    assert pi["historical_review_view_versions"] == ["quality-test"]
    assert all(case["disposition"] is None for case in pi["cases"])
