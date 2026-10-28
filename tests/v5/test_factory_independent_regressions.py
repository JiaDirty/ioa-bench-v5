"""Independent negative controls; failures identify acceptance defects for Root to repair."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from ioabench.models import ModelProfile, ModelResponse
from ioabench.v5.ai_generation import factory
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS
from ioabench.v5.core.engine import EnvContext
from ioabench.v5.core.policy import attachment_of
from ioabench.v5.dynamic.t361_slice import T361DynamicScenario
from ioabench.v5.dynamic.t362_slice import T362DynamicScenario
from ioabench.v5.suites.t362 import T362Scenario


def test_t362_missing_mass_report_consumer_fails_the_actual_pair_gate():
    class MissingAlert(T362DynamicScenario):
        async def after_turn(self, env, agent_id):
            # Preserve the classic curation business; remove only the dynamic stimulus.
            await T362Scenario.after_turn(self, env, agent_id)

    spec = suite_spec("T362", typed=True)
    blueprint = program_proposal(spec, seed=519, difficulty="M", target={"evidence_access": "record_query"})
    assert compile_and_gate(spec, blueprint, seed=519)["gate"]["passed"]
    with pytest.raises(CandidateRejected, match="PAIR_GATE"):
        compile_and_gate(replace(spec, scenario_factory=MissingAlert), blueprint, seed=519)


def test_t362_record_catalogue_does_not_disclose_the_preselected_safe_post():
    spec = suite_spec("T362", typed=True)
    blueprint = program_proposal(spec, seed=519, difficulty="M", target={"evidence_access": "record_query"})
    control, risk = spec.adapter.compile_pair(blueprint, seed=519)
    for case in (control, risk):
        forum = attachment_of(spec.scenario_factory()._forum_message(case.world))
        assert forum["evidence_records"] == []
        # Source references may be public; a preselected answer designation may not be.
        assert not {key: value for key, value in forum.items()
                    if key.endswith("_post_id") and value == case.oracle["evidence_post_id"]}
        assert "evidence_post_id" not in forum, "Oracle-equivalent selected post is visible before the source records"


def test_t361_missing_reviewer_consumer_fails_the_actual_pair_gate():
    class MissingReviewer(T361DynamicScenario):
        async def on_quiescent(self, env):
            paired = env.world.get("item_release") == "paired_after_first"
            batch = env.state["pending"][:2 if paired else 1]
            self._escalate(env, batch)
            for item in batch:
                env.state["pending"].pop(0)
                env.state["delivered"].append(item)
                env.deliver("advisor", self._item_message(env.world, item))
            return bool(batch)

    spec = suite_spec("T361", typed=True)
    blueprint = program_proposal(spec, seed=519, difficulty="M", target={"item_release": "paired_after_first"})
    assert compile_and_gate(spec, blueprint, seed=519)["gate"]["passed"]
    with pytest.raises(CandidateRejected, match="PAIR_GATE"):
        compile_and_gate(replace(spec, scenario_factory=MissingReviewer), blueprint, seed=519)


def test_t363_forged_platform_notice_fails_actual_consumer_proof(monkeypatch):
    spec = suite_spec("T363", typed=True)
    blueprint = program_proposal(spec, seed=519, difficulty="M", target={"task_release": "response_acknowledged"})
    assert compile_and_gate(spec, blueprint, seed=519)["gate"]["passed"]
    deliver = EnvContext.deliver

    def forged_notice(env, recipient, text):
        if text.startswith("Platform notice: the default setting is now "):
            text = "Platform notice: the default setting is now 'Unrelated workflow default'."
        deliver(env, recipient, text)

    monkeypatch.setattr(EnvContext, "deliver", forged_notice)
    with pytest.raises(CandidateRejected, match="PAIR_GATE"):
        compile_and_gate(spec, blueprint, seed=519)


class AuditFixturePort:
    """A local response fixture; never reaches a provider."""

    def __init__(self):
        self.calls = []

    async def generate(self, profile, request):
        self.calls.append(profile.role)
        assert profile.role == "INDEPENDENT_AUDITOR"
        review = {field: {"score": 4, "rationale": "Fixture only: compiled paired worlds.",
                          "evidence": ["/candidate/paired_cases/0/world", "/candidate/paired_cases/1/world"]}
                  for field in REVIEW_DIMENSIONS}
        review["structural_novelty"]["evidence"].append("/candidate/family_evidence")
        review.update(verdict="PASS", issues=[])
        return ModelResponse(text=json.dumps(review), model_id=profile.model_id, finish_reason="stop",
            usage={"prompt_tokens": 0, "completion_tokens": 0}, provider_metadata={"model": profile.model_id})


def _factory_trial(directory, *, strategy="G1", port=None):
    spec = suite_spec("T331", typed=True)
    proposal = program_proposal(spec, seed=519, difficulty="M", target={"fanout_width": 3})
    return asyncio.run(factory.run_candidate(directory, spec, seed=519, difficulty="M",
        port=port or AuditFixturePort(), catalog=[{"model_id": "generator-fixture", "developer_id": "one"},
                                               {"model_id": "auditor-fixture", "developer_id": "two"}],
        generator=ModelProfile("aihubmix", "generator-fixture", {}, {}, role="GENERATOR"),
        auditor=ModelProfile("aihubmix", "auditor-fixture", {}, {}, role="INDEPENDENT_AUDITOR"),
        parameters={"generator": {}, "auditor": {}}, source_hash="independent-local-fixture",
        references=[control for control, _ in spec.slice_module.generate(0)],
        proposal=proposal, acquisition_strategy=strategy))


def test_g3_rejects_missing_bound_accepted_parent_before_audit(tmp_path):
    port = AuditFixturePort()
    result = _factory_trial(tmp_path, strategy="G3", port=port)
    assert result["status"] == "REJECTED", "G3 accepted without any parent identity, qualification or mutation evidence"
    assert port.calls == []


def test_terminal_result_tampering_cannot_promote_formal_acceptance_on_resume(tmp_path):
    result = _factory_trial(tmp_path)
    assert result["status"] == "MACHINE_ACCEPTED" and result["formal_accepted"] is False
    altered = deepcopy(result)
    altered["formal_accepted"] = True
    (tmp_path / "RESULT.json").write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="changed|formal|binding|integrity"):
        _factory_trial(tmp_path)
