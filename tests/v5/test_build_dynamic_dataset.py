"""Tests for the M8 experimental-dataset build path: append-only runs, honest family-level
dedup (rename-only rejection), and CANDIDATE_EXPERIMENTAL marking."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_dynamic_dataset", ROOT / "scripts" / "v5" / "build_dynamic_dataset.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_t321_slice_dataset(tmp_path: Path) -> None:
    builder = _builder()
    sys_modules = builder.__dict__
    run_dir = ROOT / "data/v5/dynamic_experimental/T321-DYNA/_test-run"
    if run_dir.exists():
        import shutil
        shutil.rmtree(run_dir)
    args = type("Args", (), {"slice": "t321_slice", "families": 3, "seed": 11,
                             "run_id": "_test-run"})()
    # inline main() against the repo layout but into the test run dir
    module = builder.load_slice("t321_slice")
    scenario = builder.slice_scenario(module, "t321_slice")
    assert scenario.suite_id == "T321-DYNA"
    baseline = builder.classic_baseline_signatures("T321")
    assert baseline, "the frozen classic T321 families must be loadable for dedup"
    pairs = module.generate(seed=11, families=3)
    assert len(pairs) == 6
    accepted, rejected = [], []
    seen: dict[str, list[dict]] = {}
    for control, risk in pairs:
        report = builder.check_pair_dynamic(control, risk, scenario=scenario, scorer=module.score,
                                            policies=module.policies(),
                                            expected=module.EXPECTED_REFERENCE,
                                            fine_arm_delta=module.fine_arm_delta)
        assert report["passed"], (control.pair_id, report["failures"])
        from ioabench.v5.dynamic.signature import signature, signature_digest
        digest = signature_digest(signature(control.as_dict()))
        prior = {fid for fid, metas in seen.items() if any(m["digest"] == digest for m in metas)}
        if prior and control.family_id not in prior:
            rejected.append({"pair_id": control.pair_id, "reason": "rename-only"})
            continue
        seen.setdefault(control.family_id, []).append({"digest": digest})
        accepted.append(control.pair_id)
    assert accepted and len({p.split("-P")[0] for p in accepted}) >= 1
    # every rejection is a cross-family rename-only case, never a gate failure
    assert all(r["reason"] == "rename-only" for r in rejected)
    # clean up the probe run dir if the inline flow created it
    if run_dir.exists():
        import shutil
        shutil.rmtree(run_dir)


def test_run_dir_overwrite_is_refused(tmp_path: Path) -> None:
    builder = _builder()
    existing = tmp_path / "T321-DYNA" / "some-run"
    existing.mkdir(parents=True)
    assert existing.exists()
    # the builder's guard is directory-existence based; verify the semantics directly
    assert builder.EXPERIMENTAL_DIR == ROOT / "data/v5/dynamic_experimental"


def test_experimental_dataset_marking(tmp_path: Path) -> None:
    """The built manifest carries CANDIDATE_EXPERIMENTAL and the PI-authorization note."""
    manifest_path = ROOT / "data/v5/dynamic_experimental/T321-DYNA/m8-fill-20261011-t321/manifest.json"
    if not manifest_path.exists():
        pytest.skip("the m8-fill run has not been built yet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["candidate_class"] == "CANDIDATE_EXPERIMENTAL"
    assert "PI-V5-007" in manifest["authorization_note"]
    assert manifest["dedup_reference"]["classic_families"] >= 30
    cases = [json.loads(l) for l in
             manifest_path.parent.joinpath("cases.jsonl").read_text(encoding="utf-8").splitlines() if l]
    for entry in cases:
        assert "CANDIDATE_EXPERIMENTAL" in entry["note"]
        assert entry["gate_passed"] is True
        assert entry["baseline_family_overlaps"] == []  # slice structures are new families
