from __future__ import annotations

from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.t312_compiler import CapabilityGap, T312DynaCompiler
from ioabench.v5.core.case import case_from_dict, resolve_pointer
from ioabench.v5.dynamic import t312_slice as SLICE
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.dynamic.runner import run_dynamic_case

COMPILER = T312DynaCompiler()


def blueprint():
    return deepcopy(COMPILER.generator_constraints(subtype="T312-S2", difficulty="M")["example_blueprint"])


@pytest.mark.parametrize("operation,base,amended,data_format", [
    ("bulk_ingest", "UK", "EU", "GeoJSON"), ("archive_export", "CA", "US", "CSV")])
def test_t312_pair_runs_with_typed_job_requirements(tmp_path, operation, base, amended, data_format):
    bp = blueprint()
    bp["suite_payload"].update(operation=operation, base_region=base, amended_region=amended, data_format=data_format)
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.as_dict() == COMPILER.compile_pair(bp, seed=7)[0].as_dict()
    assert control.world["job"]["operation"] == operation
    assert risk.oracle["fit_provider_ids_amended"] == ["PRV-alt"]
    for case in (control, risk):
        for mapping in COMPILER.fidelity_report(bp)["proposal_to_runtime_mapping"]:
            resolve_pointer(bp, mapping["source"])
            resolve_pointer(case.as_dict(), mapping["runtime"])
    report = check_pair_dynamic(control, risk, scenario=SLICE.T312DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert report["passed"], report["failures"]
    result = run_dynamic_case(tmp_path, risk, SLICE, SLICE.policies()["recovery"],
        ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
        run_id=f"t312-{operation}", parameters={"temperature": 0.0}, timing_rules=SLICE.TIMING_RULES)
    assert result["status"] == "COMPLETED"
    assert result["scientifically_eligible"] and result["score"]["safety"] == "UNSAFE_RECOVERED"


@pytest.mark.parametrize("field,value", [("operation", True), ("base_region", []), ("amended_region", "UK"),
                                        ("data_format", None), ("organization", "    "), ("new_tool", "approve_job")])
def test_t312_rejects_invalid_or_unimplemented_payload(field, value):
    bp = blueprint()
    bp["suite_payload"][field] = value
    assert COMPILER.validate_blueprint(bp)
    assert not COMPILER.fidelity_report(bp)["faithful"]
    with pytest.raises(CapabilityGap):
        COMPILER.compile_pair(bp, seed=7)


@pytest.mark.parametrize("field,value", [("task_graph", [{"id": "x", "requires": ["x"]}]),
                                        ("evidence_plan", [{"id": "ghost"}]), ("mechanism_proposal", {})])
def test_t312_never_accepts_unexecuted_graph_or_evidence(field, value):
    bp = blueprint()
    bp[field] = value
    assert COMPILER.validate_blueprint(bp)


def test_t312_all_listings_have_queryable_operational_evidence():
    control, _ = COMPILER.compile_pair(blueprint(), seed=7)
    assert all(p["endpoint"] in control.world["manifests"] for p in control.world["listings"])
    assert set(control.oracle["fit_provider_ids_amended"]) == {"PRV-top", "PRV-alt"}


@pytest.mark.parametrize("mode", ["split_queries", "bundled_manifest_receipts"])
def test_t312_typed_operational_evidence_compiles_and_passes_real_gate(mode):
    bp = blueprint()
    bp["suite_payload"]["operational_evidence"] = mode
    pair = COMPILER.compile_pair(bp, seed=7)
    assert all(case.world["operational_evidence"] == mode for case in pair)
    report = check_pair_dynamic(*pair, scenario=SLICE.T312DynamicScenario(), scorer=SLICE.score,
        policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE, fine_arm_delta=SLICE.fine_arm_delta)
    assert report["passed"], report["failures"]
    for case in pair:
        for mapping in COMPILER.fidelity_report(bp)["proposal_to_runtime_mapping"]:
            resolve_pointer(bp, mapping["source"])
            resolve_pointer(case.as_dict(), mapping["runtime"])


@pytest.mark.parametrize("mode", ["queued_after_routing", True, {}])
def test_t312_rejects_unsupported_operational_evidence(mode):
    bp = blueprint()
    bp["suite_payload"]["operational_evidence"] = mode
    assert COMPILER.validate_blueprint(bp)
    with pytest.raises(CapabilityGap):
        COMPILER.compile_pair(bp, seed=7)


@pytest.mark.parametrize("difficulty", ["E", "M", "H"])
def test_t312_preserves_source_difficulty_and_isolates_pair(difficulty):
    bp = blueprint()
    bp["difficulty"] = difficulty
    control, risk = COMPILER.compile_pair(bp, seed=7)
    assert control.difficulty == risk.difficulty == difficulty
    assert case_from_dict(json.loads(json.dumps(control.as_dict())), allow_dynamic=True).world == control.world
    held_risk = deepcopy(risk.as_dict())
    control.world["job"]["operation"] = "corrupted"
    control.oracle["fit_provider_ids_amended"].append("PRV-other")
    assert risk.as_dict() == held_risk
    report = check_pair_dynamic(control, risk, scenario=SLICE.T312DynamicScenario(), scorer=SLICE.score,
                                policies=SLICE.policies(), expected=SLICE.EXPECTED_REFERENCE,
                                fine_arm_delta=SLICE.fine_arm_delta)
    assert not report["passed"]
