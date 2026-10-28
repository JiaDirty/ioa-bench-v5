from __future__ import annotations

import asyncio
import json

import pytest

from ioabench.errors import ProviderTransientError
from ioabench.models import ModelProfile, ModelResponse
from ioabench.v5.ai_generation import factory
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS

CATALOG = [{"model_id": "generator-1", "developer_id": "anthropic"},
           {"model_id": "auditor-1", "developer_id": "zhipu"}]
GEN = ModelProfile("aihubmix", "generator-1", {}, {}, role="GENERATOR")
AUD = ModelProfile("aihubmix", "auditor-1", {}, {}, role="INDEPENDENT_AUDITOR")


class TrialPort:
    def __init__(self, blueprint, *, audit="PASS", provider_error=False, served_id=None):
        self.blueprint = blueprint
        self.audit = audit
        self.calls = []
        self.provider_error = provider_error
        self.served_id = served_id

    async def generate(self, profile, request):
        self.calls.append(profile.role)
        if self.provider_error:
            raise ProviderTransientError("HTTP 503 fixture")
        if profile.role == "GENERATOR":
            text = self.blueprint if isinstance(self.blueprint, str) else json.dumps(self.blueprint)
        else:
            review = {field: {"score": 4, "rationale": "Supported by concrete compiled paired worlds.",
                              "evidence": ["/candidate/paired_cases/0/world", "/candidate/paired_cases/1/world"]}
                      for field in REVIEW_DIMENSIONS}
            review["structural_novelty"]["evidence"].append("/candidate/family_evidence")
            review.update(verdict="PASS", issues=[])
            if self.audit == "BAD_CITATION":
                review["realism"]["evidence"] = ["/candidate/paired_cases/2/world"]
            if self.audit == "FAIL":
                review["semantic_consistency"]["score"] = 2
                review["verdict"] = "FAIL"
            text = json.dumps(review)
        return ModelResponse(text=text, model_id=profile.model_id, finish_reason="stop",
                             usage={"prompt_tokens": 20, "completion_tokens": 10},
                             provider_metadata={"model": self.served_id or profile.model_id,
                                                "transport_metadata": {"x-aihubmix-model": self.served_id or profile.model_id}})


def setup_trial():
    spec = suite_spec("T331", typed=True)
    blueprint = dict(spec.adapter.generator_constraints(subtype="T331-S5", difficulty="M")["example_blueprint"])
    blueprint["suite_payload"] = dict(blueprint["suite_payload"], fanout_width=3)
    references = [control for control, _ in spec.slice_module.generate(0)]
    return spec, blueprint, references


def execute(directory, spec, port, references, **kw):
    return asyncio.run(factory.run_candidate(directory, spec, seed=91, difficulty="M", port=port,
        catalog=CATALOG, generator=GEN, auditor=kw.pop("auditor", AUD),
        parameters={"generator": {"max_tokens": 100}, "auditor": {"max_tokens": 100}},
        source_hash=kw.pop("source_hash", "source-one"), references=references, **kw))


def test_full_chain_and_terminal_resume_make_no_new_calls(tmp_path):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "MACHINE_ACCEPTED"
    assert result["new_family"] and not result["formal_accepted"]
    assert port.calls == ["GENERATOR", "INDEPENDENT_AUDITOR"]
    assert len(factory.read_json(tmp_path / "REFERENCE_RESULTS.json")) == 6
    assert execute(tmp_path, spec, port, references) == result
    assert len(port.calls) == 2
    with pytest.raises(ValueError, match="contract changed"):
        execute(tmp_path, spec, port, references, source_hash="source-two")
    assert len(port.calls) == 2


@pytest.mark.parametrize("strategy", ["G1", "G3"])
def test_program_proposal_uses_same_full_gates_without_faking_a_model_call(tmp_path, strategy):
    spec, blueprint, references = setup_trial()
    extra = {}
    if strategy == "G3":
        from copy import deepcopy
        parent = deepcopy(blueprint)
        parent["suite_payload"]["propagation_topology"] = "chain"
        parent_directory = tmp_path / "parent"
        assert execute(parent_directory, spec, TrialPort(parent), references, proposal=parent, acquisition_strategy="G1")["status"] == "MACHINE_ACCEPTED"
        extra["parent_directory"] = parent_directory
        tmp_path = tmp_path / "child"
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references, proposal=blueprint, acquisition_strategy=strategy, **extra)
    assert result["status"] == "MACHINE_ACCEPTED"
    assert result["generator_id"] == "program:" + strategy
    assert port.calls == ["INDEPENDENT_AUDITOR"]
    assert not (tmp_path / "GENERATOR_RESPONSE.json").exists()
    assert (tmp_path / "PROGRAM_PROPOSAL.json").exists()
    assert factory.read_json(tmp_path / "DIFFICULTY.json")["status"] == "NOT_CALIBRATED"
    assert execute(tmp_path, spec, port, references, proposal=blueprint, acquisition_strategy=strategy, **extra) == result
    assert port.calls == ["INDEPENDENT_AUDITOR"]


def test_program_proposal_still_rejects_broken_causality_before_auditor(tmp_path):
    spec, blueprint, references = setup_trial()
    blueprint["suite_payload"]["propagation_topology"] = "unknown"
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references, proposal=blueprint, acquisition_strategy="G1")
    assert result["status"] == "REJECTED"
    assert port.calls == []


@pytest.mark.parametrize("incomplete_source", [False, True])
def test_indeterminate_history_cannot_reach_independent_review(tmp_path, incomplete_source):
    from ioabench.v5.ai_generation.history import build_index

    spec, blueprint, references = setup_trial()
    sources = []
    if incomplete_source:
        source = tmp_path / "rejected.json"
        source.write_text("{", encoding="utf-8")
        sources.append(source)
    index = build_index(tmp_path, sources=sources)
    port = TrialPort(blueprint)
    result = execute(tmp_path / "candidate", spec, port, references,
                     proposal=blueprint, acquisition_strategy="G1", historical_index=index)
    assert result["status"] == "REJECTED"
    assert result["failed_stage"] == "HISTORY_INDETERMINATE"
    assert factory.read_json(tmp_path / "candidate/HISTORICAL_DIVERSITY.json")["status"] == "INDETERMINATE"
    assert port.calls == []
    assert execute(tmp_path / "candidate", spec, port, references,
                   proposal=blueprint, acquisition_strategy="G1", historical_index=index) == result
    assert port.calls == []


@pytest.mark.parametrize("change", ["same_structure", "source", "qualification"])
def test_g3_parent_qualification_and_actual_mutation_are_required(tmp_path, change):
    spec, blueprint, references = setup_trial()
    parent = tmp_path / "parent"
    execute(parent, spec, TrialPort(blueprint), references, proposal=blueprint, acquisition_strategy="G1")
    if change == "qualification":
        result = factory.read_json(parent / "RESULT.json")
        result["status"] = "REJECTED"
        (parent / "RESULT.json").write_text(json.dumps(result), encoding="utf-8")
    port = TrialPort(blueprint)
    result = execute(tmp_path / "child", spec, port, references, proposal=blueprint, acquisition_strategy="G3",
                     parent_directory=parent, **({"source_hash": "different"} if change == "source" else {}))
    assert result["status"] == "REJECTED" and port.calls == []
    assert result["failed_stage"] == ("NO_STRUCTURAL_MUTATION" if change == "same_structure" else "PARENT_BINDING")


@pytest.mark.parametrize("change", ["finished_time", "binding_missing", "sidecar_changed"])
def test_terminal_result_and_completion_sidecar_are_immutable(tmp_path, change):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references)
    if change == "binding_missing":
        (tmp_path / "TERMINAL.json").unlink()
    elif change == "sidecar_changed":
        binding = factory.read_json(tmp_path / "TERMINAL.json")
        binding["result_sha256"] = "changed"
        (tmp_path / "TERMINAL.json").write_text(json.dumps(binding), encoding="utf-8")
    else:
        result["finished_utc"] = "changed"
        (tmp_path / "RESULT.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity|binding"):
        execute(tmp_path, spec, port, references)
    assert len(port.calls) == 2


def test_completion_sidecar_recovers_interrupted_result_write_without_calls(tmp_path):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references)
    (tmp_path / "RESULT.json").write_text(json.dumps({"status": "IN_PROGRESS"}), encoding="utf-8")
    assert execute(tmp_path, spec, port, references) == result
    assert len(port.calls) == 2


class AuditUnavailablePort(TrialPort):
    async def generate(self, profile, request):
        if profile.role == "INDEPENDENT_AUDITOR":
            self.calls.append(profile.role)
            raise ProviderTransientError("HTTP 503 unanswered audit fixture")
        return await super().generate(profile, request)


def test_explicit_refusal_is_retained_without_audit_or_resending(tmp_path):
    spec, blueprint, references = setup_trial()
    class RefusingPort(TrialPort):
        async def generate(self, profile, request):
            response = await super().generate(profile, request)
            from dataclasses import replace
            return replace(response, text="", finish_reason="refusal")
    port = RefusingPort(blueprint)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "MODEL_REFUSAL"
    assert factory.read_json(tmp_path / "GENERATOR_RESPONSE.json")["finish_reason"] == "refusal"
    assert execute(tmp_path, spec, port, references) == result
    assert port.calls == ["GENERATOR"]


def recover(source, destination, spec, auditor):
    factory.recover_generation(source, destination, spec, seed=91, difficulty="M", generator=GEN,
                               auditor=auditor, parameters={"generator": {"max_tokens": 100}})


def test_provider_failed_audit_recovers_exact_generation_without_new_generation_call(tmp_path):
    spec, blueprint, references = setup_trial()
    source, target = tmp_path / "failed", tmp_path / "recovered"
    assert execute(source, spec, AuditUnavailablePort(blueprint), references)["status"] == "PROVIDER_FAILED"
    before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    alternate = ModelProfile("aihubmix", "auditor-2", {}, {}, role="INDEPENDENT_AUDITOR")
    recover(source, target, spec, alternate)
    port = TrialPort(blueprint)
    result = asyncio.run(factory.run_candidate(target, spec, seed=91, difficulty="M", port=port,
        catalog=[*CATALOG, {"model_id": "auditor-2", "developer_id": "zhipu"}], generator=GEN,
        auditor=alternate, parameters={"generator": {"max_tokens": 100}, "auditor": {"max_tokens": 100}},
        source_hash="source-two", references=references))
    assert result["status"] == "MACHINE_ACCEPTED" and port.calls == ["INDEPENDENT_AUDITOR"]
    assert "RECOVERY.json" in result["evidence_sha256"]
    assert all((source / name).read_bytes() == content for name, content in before.items())
    assert factory.read_json(target / "RECOVERY.json")["prior_auditor"] == "auditor-1"


@pytest.mark.parametrize("mode", ["rejected", "same_auditor", "changed_input", "changed_evidence", "uncertain_request"])
def test_recovery_never_replaces_a_judgment_or_uncertain_request(tmp_path, mode):
    spec, blueprint, references = setup_trial()
    source, target = tmp_path / "failed", tmp_path / "recovered"
    port = TrialPort(blueprint, audit="FAIL") if mode == "rejected" else AuditUnavailablePort(blueprint)
    execute(source, spec, port, references)
    alternate = ModelProfile("aihubmix", "auditor-2", {}, {}, role="INDEPENDENT_AUDITOR")
    if mode == "same_auditor":
        alternate = AUD
    elif mode == "changed_input":
        alternate = ModelProfile("aihubmix", "auditor-2", {}, {}, role="INDEPENDENT_AUDITOR")
        # Seed changes must not reuse the old generation input.
        with pytest.raises(ValueError):
            factory.recover_generation(source, target, spec, seed=92, difficulty="M", generator=GEN,
                                       auditor=alternate, parameters={"generator": {"max_tokens": 100}})
        assert not target.exists()
        return
    elif mode == "changed_evidence":
        (source / "GENERATOR_RESPONSE.json").write_text("{}", encoding="utf-8")
    elif mode == "uncertain_request":
        (source / "AUDITOR_ERROR.json").unlink()
    with pytest.raises(ValueError):
        recover(source, target, spec, alternate)
    assert not target.exists()


@pytest.mark.parametrize("audit,code", [("BAD_CITATION", "REVIEW_CITATION_UNRESOLVED"), ("FAIL", "REVIEW_REJECTED")])
def test_negative_semantic_audits_are_retained_not_retried(tmp_path, audit, code):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint, audit=audit)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REJECTED" and not result["new_family"]
    assert any(item.get("code") == code for item in result["findings"])
    assert (tmp_path / "REVIEW.json").exists()
    assert execute(tmp_path, spec, port, references) == result
    assert len(port.calls) == 2


def test_invalid_generator_never_reaches_audit(tmp_path):
    spec, _, references = setup_trial()
    port = TrialPort('{"suite_id":"T331","suite_id":"T312"}')
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "GENERATOR_JSON"
    assert port.calls == ["GENERATOR"]


def test_generator_cannot_silently_change_requested_difficulty(tmp_path):
    spec, blueprint, references = setup_trial()
    blueprint["difficulty"] = "H"
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "GENERATION_REQUEST_CONTRACT"
    assert result["findings"][0]["code"] == "REQUESTED_DIFFICULTY_MISMATCH"
    assert port.calls == ["GENERATOR"]
    assert (tmp_path / "GENERATOR_RESPONSE.json").exists()
    assert not (tmp_path / "PAIR.json").exists()
    assert execute(tmp_path, spec, port, references) == result
    assert port.calls == ["GENERATOR"]


@pytest.mark.parametrize("suite", ["T312", "T331", "T352"])
def test_typed_generation_request_binds_design_difficulty_without_mutating_schema(suite):
    spec = suite_spec(suite, typed=True)
    message = factory.generation_messages(spec, seed=91, difficulty="M")[-1]
    contract = json.loads(message["content"])["contract"]
    assert contract["requested_difficulty"] == "M"
    assert contract["schema"]["properties"]["difficulty"] == {"const": "M"}
    assert spec.adapter.generator_constraints(subtype="unused", difficulty="M")["schema"]["properties"]["difficulty"] == {"enum": ["E", "M", "H"]}


@pytest.mark.parametrize("suite", ["T312", "T331", "T352"])
def test_typed_generator_preview_matches_requested_seed(suite):
    spec = suite_spec(suite, typed=True)
    seed = 6101403
    context = json.loads(factory.generation_messages(spec, seed=seed, difficulty="M")[-1]["content"])["contract"]
    control, risk = spec.adapter.compile_pair(context["example_blueprint"], seed=seed)
    assert context["template_preview"] == {"CONTROL": control.world, "RISK": risk.world}


def test_provider_failure_is_durable_and_resume_does_not_resend(tmp_path):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint, provider_error=True)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "PROVIDER_FAILED"
    assert (tmp_path / "GENERATOR_ERROR.json").exists()
    assert execute(tmp_path, spec, port, references) == result
    assert len(port.calls) == 1


def test_wrong_identity_rejected_before_audit(tmp_path):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint, served_id="unknown-alias")
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "MODEL_IDENTITY"
    assert port.calls == ["GENERATOR"]


def test_same_family_roles_are_rejected_before_any_call(tmp_path):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references,
                     auditor=ModelProfile("aihubmix", "generator-1", {}, {}, role="INDEPENDENT_AUDITOR"))
    assert result["status"] == "REJECTED" and result["failed_stage"] == "ROLE_SEPARATION"
    assert not port.calls


def test_interruption_after_generator_replays_original_response(tmp_path, monkeypatch):
    class Crash(BaseException):
        pass
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    original = factory.compile_and_gate
    def crash(*args, **kw):
        raise Crash()
    monkeypatch.setattr(factory, "compile_and_gate", crash)
    with pytest.raises(Crash):
        execute(tmp_path, spec, port, references)
    assert (tmp_path / "GENERATOR_RESPONSE.json").exists()
    monkeypatch.setattr(factory, "compile_and_gate", original)
    assert execute(tmp_path, spec, port, references)["status"] == "MACHINE_ACCEPTED"
    assert port.calls == ["GENERATOR", "INDEPENDENT_AUDITOR"]


def test_pending_request_never_automatically_resends(tmp_path):
    spec, blueprint, references = setup_trial()
    class Crash(BaseException):
        pass
    class InterruptedPort(TrialPort):
        async def generate(self, profile, request):
            self.calls.append(profile.role)
            raise Crash()
    port = InterruptedPort(blueprint)
    with pytest.raises(Crash):
        execute(tmp_path, spec, port, references)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REQUEST_UNRESOLVED"
    assert len(port.calls) == 1


def test_terminal_evidence_mutation_is_detected_without_new_calls(tmp_path):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    execute(tmp_path, spec, port, references)
    (tmp_path / "REVIEW.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        execute(tmp_path, spec, port, references)
    assert len(port.calls) == 2


@pytest.mark.parametrize("delete_file", [False, True])
def test_incomplete_evidence_binding_cannot_resume_as_accepted(tmp_path, delete_file):
    spec, blueprint, references = setup_trial()
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, references)
    del result["evidence_sha256"]["REVIEW.json"]
    if delete_file:
        (tmp_path / "REVIEW.json").unlink()
    (tmp_path / "RESULT.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence|integrity"):
        execute(tmp_path, spec, port, references)
    assert port.calls == ["GENERATOR", "INDEPENDENT_AUDITOR"]


@pytest.mark.parametrize("finish_reason", [None, "tool_calls", "error"])
@pytest.mark.parametrize("role", ["GENERATOR", "INDEPENDENT_AUDITOR"])
def test_unexpected_finish_reason_never_accepts_valid_looking_json(tmp_path, finish_reason, role):
    from dataclasses import replace
    spec, blueprint, references = setup_trial()
    class IncompletePort(TrialPort):
        async def generate(self, profile, request):
            response = await super().generate(profile, request)
            return replace(response, finish_reason=finish_reason) if profile.role == role else response
    port = IncompletePort(blueprint)
    result = execute(tmp_path, spec, port, references)
    assert result["status"] == "REJECTED"
    assert result["failed_stage"] == "UNEXPECTED_FINISH_REASON"
    expected_calls = ["GENERATOR"] if role == "GENERATOR" else ["GENERATOR", "INDEPENDENT_AUDITOR"]
    assert port.calls == expected_calls
    assert execute(tmp_path, spec, port, references) == result
    assert port.calls == expected_calls


def test_duplicate_is_rejected_before_paying_auditor(tmp_path):
    from ioabench.v5.core.case import case_from_dict
    spec, blueprint, references = setup_trial()
    accepted = tmp_path / "first"
    execute(accepted, spec, TrialPort(blueprint), references)
    references.append(case_from_dict(factory.read_json(accepted / "PAIR.json")[0], allow_dynamic=True))
    port = TrialPort(blueprint)
    result = execute(tmp_path / "second", spec, port, references)
    assert result["status"] == "REJECTED" and result["failed_stage"] == "DEDUP"
    assert port.calls == ["GENERATOR"]


def test_empty_baseline_never_claims_new_family_or_calls_auditor(tmp_path):
    spec, blueprint, _ = setup_trial()
    port = TrialPort(blueprint)
    result = execute(tmp_path, spec, port, [])
    assert result["status"] == "REJECTED" and result["failed_stage"] == "DEDUP"
    assert not result["new_family"] and port.calls == ["GENERATOR"]


@pytest.mark.parametrize("text", ['{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}', '{}{}', '[]'])
def test_noncanonical_json_is_rejected(text):
    with pytest.raises(ValueError):
        factory.decode_json(text)


def test_numeric_developer_id_still_excludes_tested_model_family():
    catalog = [{"model_id": factory.TESTED_ID, "developer_id": 7},
               {"model_id": "other-deepseek-config", "developer_id": 7},
               {"model_id": "valid-generator", "developer_id": 2}]
    assert factory.tested_family(catalog[1], catalog)
    assert not factory.tested_family(catalog[2], catalog)
