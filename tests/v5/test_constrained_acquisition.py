from __future__ import annotations

import asyncio
from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile, ModelResponse
from ioabench.v5.ai_generation.acquisition import program_proposal, proposal_contract
from ioabench.v5.ai_generation.factory import run_candidate, read_json
from ioabench.v5.ai_generation.pipeline import CandidateRejected, suite_spec
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS


def test_program_mutation_consumes_structure_and_rejects_cosmetic_or_unknown_fields():
    spec = suite_spec("T331", typed=True)
    parent = program_proposal(spec, seed=41, difficulty="M")
    child = program_proposal(spec, seed=41, difficulty="M", parent=parent,
                             target={"propagation_topology": "chain"})
    assert child["suite_payload"]["propagation_topology"] == "chain"
    with pytest.raises(CandidateRejected, match="NO_STRUCTURAL_MUTATION"):
        program_proposal(spec, seed=41, difficulty="M", parent=parent,
                         target={"organization": "Another Operations"})
    with pytest.raises(CandidateRejected, match="ACQUISITION_CONSTRAINT"):
        program_proposal(spec, seed=41, difficulty="M", target={"unknown_tool": "write_bank"})


class StagePort:
    def __init__(self, blueprint, break_reference=False):
        self.blueprint, self.break_reference, self.calls = blueprint, break_reference, []

    async def generate(self, profile, request):
        self.calls.append(profile.role)
        if profile.role == "GENERATOR":
            context = json.loads(request.messages[-1]["content"])
            schema = context["output_schema"]
            name = schema["properties"]["stage"]["const"]
            fields = schema["properties"]["proposal"]["properties"]
            source = self.blueprint["suite_payload"] if name == "world_graph" or (name == "surface_artifacts" and "world_edits" not in fields) else self.blueprint
            proposal = {key: deepcopy(source[key]) if key in source else value["const"]
                        for key, value in fields.items() if key in source or "const" in value}
            value = {"stage": name, "depends_on": schema["properties"]["depends_on"]["const"], "proposal": proposal}
            if self.break_reference:
                value["depends_on"] = "fabricated-parent"
        else:
            value = {field: {"score": 4, "rationale": "Supported by concrete compiled paired worlds.",
                            "evidence": ["/candidate/paired_cases/0/world", "/candidate/paired_cases/1/world"]}
                     for field in REVIEW_DIMENSIONS}
            value["structural_novelty"]["evidence"].append("/candidate/family_evidence")
            value.update(verdict="PASS", issues=[])
        return ModelResponse(text=json.dumps(value), model_id=profile.model_id, finish_reason="stop",
                             usage={"prompt_tokens": 20, "completion_tokens": 10},
                             provider_metadata={"model": profile.model_id})


def execute(directory, port):
    spec = suite_spec("T331", typed=True)
    return asyncio.run(run_candidate(directory, spec, seed=41, difficulty="M", port=port,
        catalog=[{"model_id": "gen", "developer_id": "one"}, {"model_id": "audit", "developer_id": "two"}],
        generator=ModelProfile("aihubmix", "gen", {}, {}, role="GENERATOR"),
        auditor=ModelProfile("aihubmix", "audit", {}, {}, role="INDEPENDENT_AUDITOR"),
        parameters={"generator": {}, "auditor": {}}, source_hash="source-stage-test",
        references=[control for control, _ in spec.slice_module.generate(0)],
        staged_generation=True, target={"fanout_width": 3}))


def test_four_real_request_boundaries_compile_and_resume_without_calls(tmp_path):
    blueprint = program_proposal(suite_spec("T331", typed=True), seed=41, difficulty="M", target={"fanout_width": 3})
    port = StagePort(blueprint)
    result = execute(tmp_path, port)
    assert result["status"] == "MACHINE_ACCEPTED", result
    assert port.calls == ["GENERATOR"] * 4 + ["INDEPENDENT_AUDITOR"]
    assert [row["stage"] for row in read_json(tmp_path / "GENERATION_STAGES.json")] == [
        "task_design", "world_graph", "risk_placement", "surface_artifacts"]
    assert execute(tmp_path, port) == result
    assert len(port.calls) == 5


def test_bad_stage_reference_stops_before_world_or_auditor_call(tmp_path):
    blueprint = program_proposal(suite_spec("T331", typed=True), seed=41, difficulty="M")
    port = StagePort(blueprint, break_reference=True)
    result = execute(tmp_path, port)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "GENERATION_STAGE_SCHEMA"
    assert port.calls == ["GENERATOR"]


def test_staged_bounded_grammar_keeps_world_edits_and_typed_factor_separate():
    from ioabench.v5.ai_generation.acquisition import staged_proposal
    spec = suite_spec("T361", typed=True)
    blueprint = program_proposal(spec, seed=41, difficulty="M", target={"item_release": "paired_after_first"})
    port = StagePort(blueprint)

    async def call(stage, messages):
        from ioabench.models import ModelRequest
        response = await port.generate(ModelProfile("aihubmix", "gen", {}, {}, role="GENERATOR"),
                                       ModelRequest(tuple(messages), {}))
        return {"text": response.text, "resolved_model_id": "gen"}

    actual, stages = asyncio.run(staged_proposal(spec, seed=41, difficulty="M", target={"item_release": "paired_after_first"},
        call=call, decode=json.loads))
    assert actual == blueprint
    assert stages[1]["proposal"] == {"item_release": "paired_after_first"}
    assert stages[3]["proposal"] == {"world_edits": blueprint["world_edits"]}
    pair = spec.adapter.compile_pair(actual, seed=41)
    assert all(case.world["item_release"] == "paired_after_first" for case in pair)
