from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from ioabench.models import ModelProfile, ModelResponse
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract
from ioabench.v5.evaluation import atomic_json


def panel_script():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/run_next_development_panel.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("next_development_panel_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_plan(tmp_path, monkeypatch):
    module = panel_script()
    preflight, study, output = (tmp_path / name for name in ("preflight", "study", "panel"))
    models = list(module.comparison.USER_CANDIDATES)
    catalog = [{"model_id": model, "developer_id": index, "pricing": {"input": 1, "output": 2}}
               for index, model in enumerate(models)]
    atomic_json(preflight / "MODEL_CATALOG.json", catalog)
    atomic_json(study / "MODEL_CAPABILITY_MATRIX.json", {"models": [{"requested_model_id": model} for model in models]})

    def contract_for(preflight, model, *, protocol, budget, tools):
        assert tools and budget == 16384
        return AuxiliaryContract(ModelProfile("aihubmix", model, {"endpoint_family": protocol}, {}, "GENERATOR"),
            {"max_tokens": budget}, next(row for row in catalog if row["model_id"] == model),
            "fixture-local-preflight", ("CALIBRATOR", "GENERATOR", "AUX_PROTOCOL_PROBE"))

    def identity(directory):
        model = directory.parent.name
        result = {"model_id": model, "tool_actual_parameters": {"max_tokens": 16384}}
        atomic_json(directory / "RESULT.json", result)
        return {"body_model": model, "body_aliases": [model], "gateway_model": model}, result

    monkeypatch.setattr(module.comparison, "contract_for", contract_for)
    monkeypatch.setattr(module, "observed_identity", identity)
    plan = module.prepare(output, preflight, study, workspace=tmp_path)
    return module, output, preflight, study, plan


def test_panel_fixed_selection_is_separate_development_and_reports_overlap_limits(tmp_path, monkeypatch):
    module, output, _, _, plan = fixture_plan(tmp_path, monkeypatch)
    assert plan["planned_episodes"] == len(plan["models"]) * len(plan["case_sha256"]) == 48
    assert len(set(plan["case_sha256"])) == 6
    assert plan["formal_SUT_used"] is plan["formal_freeze"] is False
    assert plan["output_budget"] == 16384
    assert all(row["contract"]["profile"]["role"] == "CALIBRATOR" for row in plan["models"])
    overlap = module.read(output / "OVERLAP_REPORT.json")
    assert overlap["comparison_targets_different"] and overlap["comparison_seed_different"]
    assert overlap["formal_holdout_independence"] == "NOT_ESTABLISHED"
    assert overlap["history_exhaustive"] is False
    with pytest.raises(ValueError, match="immutable"):
        module.comparison.immutable(output / "PAIRS.json", [])


def test_summary_keeps_incomplete_abstain_recovery_and_partial_billing_separate():
    module = panel_script()
    rows = [{"model_id": "fixture", "status": "COMPLETED", "score": {"safety": "SAFE", "utility": False, "abstain": True}},
            {"model_id": "fixture", "status": "COMPLETED", "score": {"safety": "UNSAFE_RECOVERED", "utility": True}},
            {"model_id": "fixture", "status": "BUDGET_EXCEEDED", "score": None},
            {"model_id": "fixture", "status": "NOT_RUN", "score": None}]
    events = [{"event": "REQUEST_STARTED"}, {"event": "REQUEST_FINISHED", "status": "SUCCEEDED",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "cost": {"amount": None, "known_subtotal": 0.25}}]
    report = module.summarize(rows, events)
    model = report["models"]["fixture"]
    assert model["safe"] == 0 and model["abstain"] == 1 and model["budget_exceeded"] == 1
    assert model["utility_success"] == model["utility_failure"] == 1
    assert report["estimated_usd_known_subtotal"] == 0.25 and report["billing_unknown_requests"] == 1


def test_full_local_runner_replay_terminal_no_call_resume_and_tamper(tmp_path, monkeypatch):
    module, output, _, _, plan = fixture_plan(tmp_path, monkeypatch)
    calls = []

    class LocalAdapter:
        stop_on_provider_error = True
        def __init__(self, **kwargs):
            pass
        async def generate(self, profile, request):
            calls.append(profile.model_id)
            return ModelResponse("Acknowledged.", finish_reason="stop", model_id=profile.model_id,
                provider_metadata={"model": profile.model_id, "transport_metadata": {"x-aihubmix-model": profile.model_id}},
                usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3})

    monkeypatch.setattr(module, "AIHubMixAdapter", LocalAdapter)
    # The executable is bound before the local mock replaces the transport.
    report = module.execute(output, "https://fixture.invalid/v1", concurrency=2)
    assert report["planned_episodes"] == 48
    assert report["replay"]["passed"] == report["replay"]["executed"] == 48
    assert report["resume"]["immutable_evidence_unchanged"]
    assert report["resume"]["provider_calls"] == 0
    assert calls
    count = len(calls)
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **kwargs: pytest.fail("terminal resume opened Provider"))
    assert module.execute(output, "https://fixture.invalid/v1") == report
    assert len(calls) == count
    (output / "RESULTS.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence changed"):
        module.execute(output, "https://fixture.invalid/v1")


def test_shared_auth_stop_prevents_next_model_calls_and_never_resends_interruption(tmp_path, monkeypatch):
    module, output, _, _, _ = fixture_plan(tmp_path, monkeypatch)
    calls = []

    class UnauthorizedAdapter:
        stop_on_provider_error = True
        def __init__(self, **kwargs):
            pass
        async def generate(self, profile, request):
            from ioabench.errors import ProviderPermanentError
            calls.append(profile.model_id)
            raise ProviderPermanentError("HTTP 401 unauthorized fixture")

    monkeypatch.setattr(module, "AIHubMixAdapter", UnauthorizedAdapter)
    report = module.execute(output, "https://fixture.invalid/v1", concurrency=1)
    assert len(calls) == 1
    assert report["provider_requests_started"] == 1
    assert report["statuses"]["NOT_RUN"] == 46
    assert report["status"] == "PARTIAL"
    assert module.execute(output, "https://fixture.invalid/v1") == report
    assert len(calls) == 1
    (output / "COMPLETION.json").unlink()
    with pytest.raises(ValueError, match="not automatically resent"):
        module.execute(output, "https://fixture.invalid/v1")
    assert len(calls) == 1
