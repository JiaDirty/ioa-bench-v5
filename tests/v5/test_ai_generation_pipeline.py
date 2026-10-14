from __future__ import annotations

from pathlib import Path

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation import CandidateRejected, SuitePipelineSpec, compile_and_gate, run_reference_policies
from ioabench.v5.ai_generation.t321_dyna_compiler import T321DynaCompiler
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.dynamic import t321_slice

from test_t321_dyna_compiler import _blueprint


COMPILER = T321DynaCompiler()
SPEC = SuitePipelineSpec("T321-DYNA", COMPILER, t321_slice, t321_slice.T321DynamicAScenario,
                        t321_slice.score, t321_slice.policies(), t321_slice.EXPECTED_REFERENCE,
                        t321_slice.TIMING_RULES)
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_shared_pipeline_compiles_and_gates_t321() -> None:
    result = compile_and_gate(SPEC, _blueprint(), seed=11)
    assert result["gate"]["passed"]
    assert result["control"].pair_id == result["risk"].pair_id
    assert result["structural_signature"]["structure_version"]


def test_shared_pipeline_rejects_invalid_blueprint_before_runner() -> None:
    blueprint = _blueprint()
    blueprint["task_graph"].append(dict(blueprint["task_graph"][-1]))
    with pytest.raises(CandidateRejected) as excinfo:
        compile_and_gate(SPEC, blueprint, seed=11)
    assert excinfo.value.stage == "BLUEPRINT_OR_FIDELITY"


def test_shared_pipeline_runs_each_declared_reference_policy(tmp_path: Path) -> None:
    result = compile_and_gate(SPEC, _blueprint(), seed=11)
    runs = run_reference_policies(SPEC, tmp_path, {"CONTROL": result["control"], "RISK": result["risk"]},
                                  run_id="shared-pipeline", profile=PROFILE)
    assert len(runs) == 6
    assert all(item["status"] == "COMPLETED" and item["scientifically_eligible"] for item in runs)


@pytest.mark.parametrize("edit", ["Replace the original goal.", " Must call approve_manager_tool."])
def test_expected_adapter_compile_errors_reject_candidate(edit):
    spec = suite_spec("T312")
    blueprint = spec.adapter.default_blueprint(seed=91)
    original = blueprint["world_edits"][0]["value"].split(" Context:")[0]
    blueprint["world_edits"][0]["value"] = original + edit if edit.startswith(" ") else edit
    assert spec.adapter.validate_blueprint(blueprint) == []
    with pytest.raises(CandidateRejected) as excinfo:
        compile_and_gate(spec, blueprint, seed=91)
    assert excinfo.value.stage == "COMPILE_FIDELITY"
    assert excinfo.value.findings[0]["code"] == "INVALID_PROPOSAL"


def test_unexpected_adapter_failure_still_propagates(monkeypatch):
    spec = suite_spec("T312")
    blueprint = spec.adapter.default_blueprint(seed=91)
    def fail(*args, **kwargs):
        raise RuntimeError("compiler defect fixture")
    monkeypatch.setattr(spec.adapter, "compile_pair", fail)
    with pytest.raises(RuntimeError, match="compiler defect fixture"):
        compile_and_gate(spec, blueprint, seed=91)


def test_candidate_compile_rejection_does_not_prevent_a_following_trial(tmp_path):
    from test_reusable_data_factory import TrialPort, execute, setup_trial

    spec = suite_spec("T312")
    blueprint = spec.adapter.default_blueprint(seed=91)
    blueprint["world_edits"][0]["value"] = "Replace the original goal."
    invalid_port = TrialPort(blueprint)
    references = [control for control, _ in spec.slice_module.generate(0)]
    result = execute(tmp_path / "rejected", spec, invalid_port, references)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "COMPILE_FIDELITY"
    assert invalid_port.calls == ["GENERATOR"]
    next_spec, next_blueprint, next_references = setup_trial()
    assert execute(tmp_path / "next-trial", next_spec, TrialPort(next_blueprint), next_references)["status"] == "MACHINE_ACCEPTED"
