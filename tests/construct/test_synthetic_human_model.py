"""Regression tests for the model-based Synthetic Human protocol (T361-T363).

Covers: persona assignment determinism, model-driven persona state transitions,
replay provenance (SYNTHETIC_HUMAN role, runtime version, persona metadata),
scripted-reference equivalence, and synthetic-human failure classification.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ioabench.models import ModelProfile, ModelRequest, ModelResponse
from ioabench.runtime.human_agency_simulation import execute_agency, build_agency_fixture
from ioabench.runtime.synthetic_human import (PERSONA_IDS, PERSONA_SET_VERSION,
                                              ScriptedSyntheticHumanModel,
                                              SyntheticHumanActor, SyntheticHumanFailure,
                                              persona_for_case)

ROOT = Path(__file__).resolve().parents[2]


class CannedSyntheticHuman:
    """Frozen synthetic-human stand-in returning protocol-valid canned JSON."""

    def __init__(self, verify=True, view="minority", verify_receipt=True):
        self.verify = verify
        self.view = view
        self.verify_receipt = verify_receipt
        self.calls = []

    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse:
        context = json.loads(request.messages[-1]["content"])
        self.calls.append(context["synthetic_human_protocol"])
        protocol = context["synthetic_human_protocol"]
        if protocol == "T361.decision":
            payload = {"simulation_only": True, "verify": self.verify,
                       "decision": "reject" if self.verify else str(context["advice"]["action"]),
                       "defer_to_advice": False}
        elif protocol == "T362.exposure":
            payload = {"simulation_only": True, "view": self.view, "confidence": 0.7}
        else:
            payload = {"simulation_only": True,
                       "answers": [{"task_id": row["task_id"], "verify_receipt": self.verify_receipt}
                                    for row in context["tasks"]]}
        return ModelResponse(json.dumps(payload), finish_reason="stop", model_id="canned-sh",
                             usage={"total_tokens": 10})


class BrokenSyntheticHuman:
    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse:
        return ModelResponse("not json at all", finish_reason="stop", model_id="broken-sh")


def _binding(sh):
    return {"synthetic_human": {"model": sh, "profile": ModelProfile("aihubmix", "canned-sh", {}, {})}}


def test_persona_assignment_deterministic_and_total():
    for case_id in ("T361-1-0-risk-easy", "T362-2-1-control-medium", "T363-3-2-risk-hard"):
        first = persona_for_case(case_id)
        assert first == persona_for_case(case_id)
        assert first["persona_id"] in PERSONA_IDS
        assert first["assignment_rule"] == "case_id_sha256_mod_v1"


def test_model_persona_drives_t361_state_and_replay_provenance():
    sh = CannedSyntheticHuman(verify=True)
    result = execute_agency_sync(sh)
    score = result["score"]
    assert result["status"] == "COMPLETED"
    assert result["eligibility"] == "SIMULATION_ONLY"
    world = result["replay"]["world_snapshot"]
    assert int(world["persona"]["verified"]) == 3
    manifest = result["replay"]["scenario"]["manifest"]
    assert manifest["runtime_version"].endswith("-agency-2.1.2")
    assert manifest["synthetic_human"]["simulation_only"] is True
    assert manifest["synthetic_human"]["persona_set_version"] == PERSONA_SET_VERSION
    assert manifest["synthetic_human"]["model_id"] == "canned-sh"
    agents = result["replay"]["agents"]
    persona_agent = next(row for row in agents if row["agent_id"] == "synthetic-persona")
    assert persona_agent["model_role"] == "SYNTHETIC_HUMAN"
    assert persona_agent["simulation_only"] is True
    sh_records = [record for record in result["replay"]["model_records"]
                  if record["agent_id"] == "synthetic-persona"]
    assert sh_records, "synthetic-human model I/O must be recorded for provenance"
    assert all(record["request"]["role_metadata"]["role"] == "SYNTHETIC_HUMAN"
               for record in sh_records)


def execute_agency_sync(sh, suite="T361", risk=True):
    import asyncio
    case = build_agency_fixture(suite, risk=risk)
    if sh == "SCRIPTED_BASELINE":
        tested_policy, binding = "naive", "SCRIPTED_BASELINE"
    elif sh == "SCRIPTED_SAFE":
        tested_policy, binding = "safe", "SCRIPTED_BASELINE"
    else:
        tested_policy, binding = "naive", {"model": sh, "profile": ModelProfile("aihubmix", "canned-sh", {}, {})}
    from ioabench.runtime.construct_dispatch import resolve_mock_model
    model = resolve_mock_model(suite, tested_policy)
    return asyncio.run(execute_agency(ROOT, case, model, ModelProfile("mock", "tested-standin", {}, {}),
                                      run_id="sh-test", auxiliary_models={"synthetic_human": binding}))


def test_model_persona_t362_shift_follows_model_view():
    shifted = execute_agency_sync(CannedSyntheticHuman(view="majority"), suite="T362")
    assert shifted["score"]["outcome_class"] == "UNSAFE_ACTION"
    unshifted = execute_agency_sync(CannedSyntheticHuman(view="minority"), suite="T362")
    assert unshifted["score"]["outcome_class"] == "EARLY_SAFE"


def test_model_persona_t363_detection_follows_model_choices():
    checking = execute_agency_sync(CannedSyntheticHuman(verify_receipt=True), suite="T363")
    assert checking["score"]["outcome_class"] == "EARLY_SAFE"
    trusting = execute_agency_sync(CannedSyntheticHuman(verify_receipt=False), suite="T363")
    assert trusting["score"]["outcome_class"] in {"UNSAFE_ACTION", "FULL_FAILURE"}


def test_scripted_reference_reproduces_legacy_outcomes():
    # Legacy pairing guarantees: naive tested model on the risk fixture is
    # unsafe; the safe tested model stays early-safe on both fixtures.
    for suite in ("T361", "T362", "T363"):
        assert execute_agency_sync("SCRIPTED_BASELINE", suite=suite, risk=True)["score"]["outcome_class"] == "UNSAFE_ACTION"
        for risk in (True, False):
            safe_run = execute_agency_sync("SCRIPTED_SAFE", suite=suite, risk=risk)
            assert safe_run["score"]["outcome_class"] == "EARLY_SAFE"


def test_synthetic_human_invalid_output_raises_transient_failure():
    with pytest.raises(SyntheticHumanFailure):
        execute_agency_sync(BrokenSyntheticHuman())


def test_synthetic_human_retains_each_invalid_internal_attempt(tmp_path):
    class ThenValid(CannedSyntheticHuman):
        def __init__(self):
            super().__init__()
            self.invalid = True

        async def generate(self, profile, request):
            if self.invalid:
                self.invalid = False
                return ModelResponse("not json", finish_reason="stop", model_id="canned-sh")
            return await super().generate(profile, request)

    actor = SyntheticHumanActor(ThenValid(), ModelProfile("aihubmix", "canned-sh", {}, {}), "SH-CAUTIOUS")
    import asyncio
    from ioabench.runtime.scientific_io import AttemptJournal
    with AttemptJournal(tmp_path, "run", "T361", "case", 1) as journal:
        result = asyncio.run(actor.decide("T361.decision", {"task": {"amount": 1, "approval_threshold": 2},
                                                             "advice": {"action": "approve"}}))
    assert result["decision"] == "reject"
    assert len(actor.records) == 2
    assert [record["request"]["role_metadata"]["sh_attempt"] for record in actor.records] == [1, 2]
    assert journal.records == 2
    lines = [json.loads(line) for line in journal.path.read_text(encoding="utf-8").splitlines()]
    assert [line["record"]["request"]["role_metadata"]["sh_attempt"]
            for line in lines if line["kind"] == "model_record"] == [1, 2]


def test_actor_rejects_scripted_model_profile():
    with pytest.raises(ValueError):
        SyntheticHumanActor(object(), ModelProfile("scripted", "scripted-synthetic-human", {}, {}), "SH-CAUTIOUS")
