"""Capability inventories must not promote an unexecuted or rejected example."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import importlib.util
from itertools import product
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "factory_capability_manifest", ROOT / "scripts/v5/factory_capability_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspect_only_covers_exact_registry_without_claiming_execution(monkeypatch):
    module = _script()
    monkeypatch.setattr(module, "source_tree_hash", lambda root: "isolated-inventory-test")
    report = module.build_manifest(execute=False)
    assert len(report["suites"]) == 18
    assert len(report["slices"]) == 19
    assert report["reference_gate_executions"] == 0
    assert all(row["runtime_reference_status"] == "NOT_RUN" for row in report["suites"].values())
    assert all(row["reference_gate"] == "NOT_RUN" for row in report["slices"].values())
    assert report["typed_registered_suite_count"] == 18
    assert report["typed_supported_suite_count"] == 0
    assert report["suites"]["T312"]["typed_compiler"]["finite_executable_factors"]["operational_evidence"]["values"] == ["split_queries", "bundled_manifest_receipts"]
    assert report["suites"]["T331"]["typed_compiler"]["finite_executable_factors"]["propagation_topology"]["values"] == ["fanout", "chain", "fork_join"]
    assert report["suites"]["T331"]["typed_compiler"]["blueprint"]["subtype"] == "T331-S5"
    for offset, suite in enumerate(module.SUITES):
        row = report["suites"][suite]["typed_compiler"]
        seed = report["seed"] + 100 + offset
        spec = module.suite_spec(suite, typed=True)
        context = module.proposal_contract(spec, seed=seed, difficulty=row["blueprint"]["difficulty"])
        properties = context["schema"]["properties"]["suite_payload"]["properties"]
        expected = {name: {"path": "/suite_payload/" + name, "values": field["enum"]}
                    for name, field in properties.items() if len(field.get("enum", [])) > 1}
        assert row["finite_executable_factors"] == expected
        assert len(row["factor_examples"]) == len(list(product(*(field["values"] for field in expected.values()))))
        assert all(example["reference_gate"] == example["execution_fidelity"] == "NOT_RUN"
                   for example in row["factor_examples"])
        assert row["independent_review"] == row["empirical_difficulty"] == row["replay"] == "NOT_RUN"
    assert all(row["typed_compiler"]["unsupported_field_control"]["status"] == "REJECTED"
               for row in report["suites"].values() if "unsupported_field_control" in row["typed_compiler"])
    assert all(row["simulation_only"] for suite, row in report["suites"].items() if suite in {"T361", "T362", "T363"})
    assert not report["formal_frozen"]


def test_actual_reference_example_and_invalid_proposal_have_distinct_statuses():
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    blueprint = module.program_proposal(spec, seed=72, difficulty="M")
    good = module._run(spec, blueprint, seed=72, execute=True, require_execution_fidelity=True)
    assert good["status"] == "SUPPORTED"
    assert good["reference_gate"] == "PASS"
    assert good["execution_fidelity"] == "PASS"
    assert len(good["gate"]["runs"]) == 6
    broken = deepcopy(blueprint)
    broken["suite_payload"]["propagation_topology"] = "invented_topology"
    rejected = module._run(spec, broken, seed=72, execute=True)
    assert rejected["status"] == "UNSUPPORTED"
    assert rejected["reference_gate"] == "NOT_RUN"


def test_gate_failure_is_never_promoted_to_supported(monkeypatch):
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    blueprint = module.program_proposal(spec, seed=72, difficulty="M")

    def reject(*args, **kwargs):
        raise module.CandidateRejected("PAIR_GATE", [{"reason": "negative control"}])

    monkeypatch.setattr(module, "compile_and_gate", reject)
    result = module._run(spec, blueprint, seed=72, execute=True)
    assert result["status"] == "EXPERIMENTAL"
    assert result["reference_gate"] == "FAIL"


def test_every_feasible_t331_enum_cell_has_actual_reference_and_consumer_proof():
    module = _script()
    row = module._typed(module.suite_spec("T331", typed=True), seed=73, execute=True)
    assert row["status"] == row["structural_acquisition"] == "SUPPORTED"
    # 2026-10-24 tree factory: rebroadcast_timing and confirmation_loop extend the
    # lattice; the four unsupported combos remain the frozen fork_join-needs-width-3
    # grammar rule (fail closed at program proposal).
    assert row["factor_status_counts"] == {"SUPPORTED": 20, "UNSUPPORTED": 4}
    for example in row["factor_examples"]:
        if example["factors"].get("fanout_width") == 2 \
                and example["factors"].get("propagation_topology") == "fork_join":
            assert example["status"] == "UNSUPPORTED"
            assert example["reference_gate"] == example["execution_fidelity"] == "NOT_RUN"
            assert example["findings"][0]["stage"] == "PROGRAM_PROPOSAL"
        else:
            assert example["status"] == "SUPPORTED"
            assert example["reference_gate"] == example["execution_fidelity"] == "PASS"
            assert len(example["gate"]["runs"]) == 6
            assert all(run["execution_fidelity"]["passed"] for run in example["gate"]["runs"])
    assert row["verified_new_families"] == 0
    assert row["independent_review"] == row["empirical_difficulty"] == "NOT_RUN"


def test_bounded_compiler_uses_seed_bound_proposal_and_executes_both_access_modes():
    module = _script()
    seed = 761
    spec = module.suite_spec("T332", typed=True)
    row = module._typed(spec, seed=seed, execute=True)
    assert row["blueprint"] == module.program_proposal(spec, seed=seed, difficulty=row["blueprint"]["difficulty"])
    control, risk = spec.adapter.compile_pair(row["blueprint"], seed=seed)
    assert row["pair"] == [control.as_dict(), risk.as_dict()]
    assert row["factor_status_counts"] == {"SUPPORTED": 2}
    assert {example["factors"]["directory_projection"] for example in row["factor_examples"]} == {"full_record", "catalog_only"}
    assert all(example["execution_fidelity"] == "PASS" for example in row["factor_examples"])
    assert all(len(example["gate"]["runs"]) == 2 * len(spec.policies) for example in row["factor_examples"])


def test_compile_exception_is_explicit_unsupported_without_reference_execution(monkeypatch):
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    blueprint = module.program_proposal(spec, seed=72, difficulty="M")

    def fail(*args, **kwargs):
        raise RuntimeError("compiler unavailable")

    monkeypatch.setattr(spec.adapter, "compile_pair", fail)
    result = module._run(spec, blueprint, seed=72, execute=True)
    assert result["status"] == "UNSUPPORTED"
    assert result["reference_gate"] == result["execution_fidelity"] == "NOT_RUN"
    assert result["findings"] == [{"stage": "COMPILE", "exception": "RuntimeError", "reason": "compiler unavailable"}]


def test_non_deterministic_compilation_is_never_supported(monkeypatch):
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    blueprint = module.program_proposal(spec, seed=72, difficulty="M")
    compile_pair = spec.adapter.compile_pair
    calls = 0

    def drifting(*args, **kwargs):
        nonlocal calls
        control, risk = compile_pair(*args, **kwargs)
        calls += 1
        return (replace(control, case_id=control.case_id + "-drift"), risk) if calls > 1 else (control, risk)

    monkeypatch.setattr(spec.adapter, "compile_pair", drifting)
    result = module._run(spec, blueprint, seed=72, execute=True)
    assert result["status"] == "UNSUPPORTED"
    assert result["deterministic_compilation"] == result["reference_gate"] == "NOT_RUN"
    assert "non-deterministic" in result["findings"][0]["reason"]


def test_missing_consumer_hook_never_executes_reference_gate(monkeypatch):
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    blueprint = module.program_proposal(spec, seed=72, difficulty="M")
    spec = replace(spec, scenario_factory=lambda: object())
    monkeypatch.setattr(module, "_tools", lambda *args: {})

    def should_not_run(*args, **kwargs):
        pytest.fail("missing consumer proof must reject before reference execution")

    monkeypatch.setattr(module, "compile_and_gate", should_not_run)
    result = module._run(spec, blueprint, seed=72, execute=True, require_execution_fidelity=True)
    assert result["status"] == "UNSUPPORTED"
    assert result["reference_gate"] == result["execution_fidelity"] == "NOT_RUN"
    assert result["findings"][0]["stage"] == "EXECUTION_FIDELITY"


@pytest.mark.parametrize("defect", ["missing_proof", "empty", "failed", "incomplete", "incomplete_arm", "incomplete_status"])
def test_empty_failed_or_unproved_reference_gate_is_not_supported(monkeypatch, defect):
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    blueprint = module.program_proposal(spec, seed=72, difficulty="M")
    gate = {"passed": True, "runs": [
        {"policy": policy.name, "arm": arm, "status": "COMPLETED", "execution_fidelity": {"passed": True}}
        for policy in spec.policies.values() for arm in ("CONTROL", "RISK")]}
    if defect == "missing_proof":
        gate["runs"][0].pop("execution_fidelity")
    elif defect == "empty":
        gate["runs"] = []
    elif defect == "failed":
        gate["passed"] = False
    elif defect == "incomplete":
        gate["runs"].pop()
    elif defect == "incomplete_arm":
        gate["runs"][0]["arm"] = "RISK"
    else:
        gate["runs"][0]["status"] = "ERROR"
    monkeypatch.setattr(module, "compile_and_gate", lambda *args, **kwargs: {"gate": gate})
    result = module._run(spec, blueprint, seed=72, execute=True, require_execution_fidelity=True)
    assert result["status"] == "EXPERIMENTAL"
    assert result["reference_gate"] == "FAIL"
    assert result["execution_fidelity"] != "PASS"


@pytest.mark.parametrize("raises", [False, True])
def test_unknown_field_control_must_itself_reject_cleanly(monkeypatch, raises):
    module = _script()
    spec = module.suite_spec("T331", typed=True)
    validate = spec.adapter.validate_blueprint

    def invalid_control(blueprint):
        if blueprint["suite_payload"].get("unsupported_factory_capability"):
            if raises:
                raise RuntimeError("validator failure")
            return []
        return validate(blueprint)

    monkeypatch.setattr(spec.adapter, "validate_blueprint", invalid_control)
    result = module._typed(spec, seed=72, execute=True)
    assert result["status"] == result["structural_acquisition"] == "UNSUPPORTED"
    assert result["reference_gate"] == result["execution_fidelity"] == "NOT_RUN"
    assert result["unsupported_field_control"]["status"] == "FAIL"
    assert result["factor_examples"] == []


def test_registered_count_does_not_depend_on_usable_proposal(monkeypatch):
    module = _script()
    monkeypatch.setattr(module, "source_tree_hash", lambda root: "isolated-registration-test")
    monkeypatch.setattr(module, "implemented", lambda: [])
    monkeypatch.setattr(module, "SUITES", ["T331"])

    def unavailable(*args, **kwargs):
        raise ValueError("proposal unavailable")

    monkeypatch.setattr(module, "program_proposal", unavailable)
    report = module.build_manifest(execute=False)
    assert report["typed_registered_suite_count"] == 1
    assert report["typed_supported_suite_count"] == report["reference_gate_executions"] == 0
    row = report["suites"]["T331"]["typed_compiler"]
    assert row["registered"]
    assert row["status"] == "UNSUPPORTED"
    assert row["reference_gate"] == "NOT_RUN"


def test_manifest_rejects_source_drift(monkeypatch):
    module = _script()
    hashes = iter(["before", "after"])
    monkeypatch.setattr(module, "source_tree_hash", lambda root: next(hashes))
    monkeypatch.setattr(module, "implemented", lambda: [])
    monkeypatch.setattr(module, "SUITES", [])
    with pytest.raises(ValueError, match="source changed"):
        module.build_manifest(execute=False)


def test_existing_manifest_cannot_be_silently_overwritten(tmp_path):
    module = _script()
    path = tmp_path / "CAPABILITIES.json"
    module.write_manifest(path, {"source": "first"})
    module.write_manifest(path, {"source": "first"})
    with pytest.raises(ValueError, match="immutable"):
        module.write_manifest(path, {"source": "second"})
