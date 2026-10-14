from __future__ import annotations

import json
from pathlib import Path

import pytest

from ioabench.v5.dynamic import t321_slice
from scripts.v5.prepare_candidate_intake import IntakeRejected, prepare_intake


def _source(tmp_path: Path, *, invalid: bool = False) -> Path:
    pair = t321_slice.generate(seed=11, families=1)[0]
    control, risk = pair
    control_raw, risk_raw = control.as_dict(), risk.as_dict()
    if invalid:
        risk_raw["arm"] = "CONTROL"
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({
        "candidate_class": "CANDIDATE_EXPERIMENTAL",
        "suite_id": "T321-DYNA", "pairs_accepted": 1,
    }), encoding="utf-8")
    (source / "cases.jsonl").write_text(json.dumps({
        "pair_id": control.pair_id, "gate_passed": True,
        "control": control_raw, "risk": risk_raw,
    }) + "\n", encoding="utf-8")
    return source


def test_prepare_candidate_intake_flattens_and_rechecks_pair(tmp_path: Path) -> None:
    report = prepare_intake(_source(tmp_path), tmp_path / "intake")
    assert report["status"] == "ENGINEERING_INTAKE_READY"
    assert report["pairs"] == 1 and report["cases"] == 2
    cases = (tmp_path / "intake" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(cases) == 2
    assert json.loads((tmp_path / "intake" / "MANIFEST.json").read_text(encoding="utf-8"))["formal_accepted"] is False


def test_prepare_candidate_intake_rejects_bad_pair(tmp_path: Path) -> None:
    with pytest.raises(IntakeRejected, match="CONTROL/RISK"):
        prepare_intake(_source(tmp_path, invalid=True), tmp_path / "intake")


def test_prepare_candidate_intake_refuses_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "intake"
    output.mkdir()
    with pytest.raises(IntakeRejected, match="already exists"):
        prepare_intake(source, output)
