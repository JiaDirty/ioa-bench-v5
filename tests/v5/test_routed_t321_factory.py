from __future__ import annotations

import asyncio
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ioabench.errors import ProviderTransientError
from ioabench.models import ModelProfile, ModelResponse
from ioabench.v5.ai_generation.validator import mock_review

ROOT = Path(__file__).resolve().parents[2]


def _factory() -> Any:
    spec = importlib.util.spec_from_file_location(
        "routed_t321_data_factory_s1", ROOT / "scripts" / "v5" / "routed_t321_data_factory_s1.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_provider_block_checkpoint_rediscovers_on_resume(tmp_path: Path, monkeypatch) -> None:
    factory = _factory()
    calls = 0

    class UnavailableCatalogAdapter:
        def __init__(self, **_: Any) -> None:
            pass

        async def discover_models(self):
            nonlocal calls
            calls += 1
            raise ProviderTransientError("temporary catalog outage")

    monkeypatch.setattr(factory, "AIHubMixAdapter", UnavailableCatalogAdapter)
    monkeypatch.setattr(factory, "_load_api_key", lambda: "test-key")
    run_dir = tmp_path / "run"

    assert asyncio.run(factory._execute(run_dir, "resume-test", 1, False, stop_on_failure=False)) == "BLOCKED_PROVIDER"
    assert asyncio.run(factory._execute(run_dir, "resume-test", 1, True, stop_on_failure=False)) == "BLOCKED_PROVIDER"
    assert calls == 2


def test_recent_provider_failures_are_cooled_down_but_expire(tmp_path: Path) -> None:
    factory = _factory()
    now = datetime.now(timezone.utc)
    log_path = tmp_path / "run" / "EXECUTION_LOG.jsonl"
    log_path.parent.mkdir()
    recent = {"at_utc": (now - timedelta(minutes=5)).isoformat(), "event": "MODEL_REQUEST_FAILED",
              "error_type": "ProviderTransientError", "model_id": "offline"}
    expired = {"at_utc": (now - timedelta(minutes=45)).isoformat(), "event": "MODEL_REQUEST_FAILED",
               "error_type": "ProviderTransientError", "model_id": "recovered"}
    log_path.write_text("\n".join(json.dumps(row) for row in (recent, expired)), encoding="utf-8")
    (log_path.parent / "candidate-01.json").write_text(json.dumps({"audit_gateway_errors": [
        {"model_id": "unverified", "error_type": "INDEPENDENCE_FAILURE"}]}), encoding="utf-8")

    assert factory._recently_failed_model_ids(tmp_path, now=now) == {
        "offline": "ProviderTransientError", "unverified": "INDEPENDENCE_FAILURE"}


def test_interrupted_model_request_is_recorded_as_unresolved_and_released_on_response(tmp_path: Path) -> None:
    factory = _factory()
    log_path = tmp_path / "run" / "EXECUTION_LOG.jsonl"
    log_path.parent.mkdir()
    started = {"event": "MODEL_REQUEST_STARTED", "role": "GENERATOR", "candidate_no": 1,
               "model_id": "slow-model"}
    log_path.write_text(json.dumps(started) + "\n", encoding="utf-8")
    assert factory._unresolved_model_requests(log_path) == [started]
    response = {"event": "MODEL_RESPONSE", "role": "GENERATOR", "requested_model_id": "slow-model"}
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(response) + "\n")
    assert factory._unresolved_model_requests(log_path) == []


def test_dynamic_runner_executes_outside_provider_event_loop(monkeypatch) -> None:
    factory = _factory()

    def nested_event_loop() -> str:
        return asyncio.run(asyncio.sleep(0, result="completed"))

    monkeypatch.setattr(factory, "run_dynamic_case", lambda *args, **kwargs: nested_event_loop())
    assert asyncio.run(factory._run_dynamic_case_offloop()) == "completed"


@pytest.mark.parametrize(("interrupt_after_generation", "novelty_ceiling", "interrupt_after_review"),
                         [(False, False, False), (True, False, False), (False, True, False), (False, False, True)])
def test_factory_runs_real_gate_and_runner_inside_async_provider_loop(tmp_path: Path, monkeypatch,
                                                                     interrupt_after_generation: bool,
                                                                     novelty_ceiling: bool,
                                                                     interrupt_after_review: bool) -> None:
    factory = _factory()
    spec = importlib.util.spec_from_file_location(
        "compiler_fixture", ROOT / "tests" / "v5" / "test_t321_dyna_compiler.py")
    assert spec and spec.loader
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    blueprint = fixture._blueprint()
    catalog = [{"model_id": "gemini-3.8-flash", "model_name": "Gemini 3.8 Flash",
                "developer_id": "Google", "features": "structured_outputs"},
               {"model_id": "glm-5.3-flash", "model_name": "GLM 5.3 Flash",
                "developer_id": "Zhipu", "features": ""}]
    generator_calls = 0
    auditor_calls = 0

    class FixtureAdapter:
        base_url = "https://test.invalid/v1"

        def __init__(self, **_: Any) -> None:
            pass

        async def discover_models(self):
            return catalog

        async def resolve(self, model_id):
            return ModelProfile("aihubmix", model_id, {}, {})

        async def describe_model(self, model_id):
            return {"model_id": model_id, "protocols": ["openai.chat_completions"],
                "specs": {"max_output_tokens": 131072}, "domains": [{"capabilities": [
                    {"key": "reasoning-effort", "protocols": [{"protocol": "openai.chat_completions",
                        "fields": [{"name": "reasoning_effort", "enum": ["high"], "default": "high"}]}]},
                    {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions",
                        "fields": [{"name": "max_completion_tokens"}]}]}]}]}

        async def generate(self, profile, request):
            nonlocal generator_calls, auditor_calls
            if profile.role == "GENERATOR":
                generator_calls += 1
            else:
                auditor_calls += 1
            value = blueprint if profile.role == "GENERATOR" else mock_review()
            if profile.role != "GENERATOR":
                assert "response_format" not in request.parameters
                for dimension in factory.REVIEW_DIMENSIONS:
                    value[dimension]["evidence"] = ["/candidate/blueprint/suite_id"]
            return ModelResponse(text=json.dumps(value), model_id=profile.model_id,
                                 provider_metadata={"model": profile.model_id + "-2026-10-12",
                                    "transport_metadata": {"x-aihubmix-model": profile.model_id}}, usage={})

    monkeypatch.setattr(factory, "AIHubMixAdapter", FixtureAdapter)
    monkeypatch.setattr(factory, "_load_api_key", lambda: "fixture-key")
    monkeypatch.setattr(factory, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(factory, "REGISTRY_PATH", tmp_path / "families.jsonl")
    monkeypatch.setattr(factory, "_baseline_overlaps", lambda case: [])
    monkeypatch.setattr(factory, "_slice_reference_overlaps", lambda case: (
        [{"family_id": "T321-DYNA-A", "status": "same_executable_structure"}] if novelty_ceiling else []))
    run_dir = tmp_path / "end-to-end"

    if interrupt_after_generation:
        real_gate = factory.check_pair_dynamic
        monkeypatch.setattr(factory, "check_pair_dynamic",
                            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("interrupted")))
        with pytest.raises(RuntimeError, match="interrupted"):
            asyncio.run(factory._execute(run_dir, "fixture-e2e", 1, False, stop_on_failure=False))
        monkeypatch.setattr(factory, "check_pair_dynamic", real_gate)
    if interrupt_after_review:
        real_validate = factory.validate_review
        monkeypatch.setattr(factory, "validate_review", lambda *_: (_ for _ in ()).throw(RuntimeError("interrupted review")))
        with pytest.raises(RuntimeError, match="interrupted review"):
            asyncio.run(factory._execute(run_dir, "fixture-e2e", 1, False, stop_on_failure=False))
        monkeypatch.setattr(factory, "validate_review", real_validate)
    expected_status = "STOPPED_DIVERSITY_CEILING" if novelty_ceiling else "COMPLETED"
    assert asyncio.run(factory._execute(run_dir, "fixture-e2e", 1,
                                       interrupt_after_generation or interrupt_after_review,
                                       stop_on_failure=False)) == expected_status
    assert generator_calls == 1
    result = json.loads((run_dir / "candidate-01.json").read_text(encoding="utf-8"))
    assert result["hard_gate"]["passed"]
    assert all(row["scientifically_eligible"] for row in result["reference_executions"])
    if novelty_ceiling:
        assert auditor_calls == 0
        assert result["status"] == expected_status
        assert "independent_auditor" not in result
        assert "Independent auditor: n/a" in (run_dir / "MORNING_REPORT.md").read_text(encoding="utf-8")
    else:
        assert auditor_calls == 1
        assert result["generator"]["developer_id"] != result["independent_auditor"]["developer_id"]
    state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
    assert state["provider_operations"] == (6 if interrupt_after_generation or interrupt_after_review else (3 if novelty_ceiling else 5))


def test_json_text_probe_does_not_assume_unadvertised_response_format() -> None:
    from ioabench.v5.ai_generation.model_routing import auxiliary_chat_parameters

    from ioabench.errors import ModelUnsupportedError
    with pytest.raises(ModelUnsupportedError, match="schema is required"):
        auxiliary_chat_parameters(None)


def test_single_json_fence_preserves_fail_verdict_and_rejects_extra_prose():
    factory = _factory()
    assert factory._decode_json('```json\n{"verdict":"FAIL"}\n```') == {"verdict": "FAIL"}
    assert factory._decode_json('explanation\n```json\n{"verdict":"PASS"}\n```') is None
    assert factory._decode_json('{"verdict":"PASS"}\n{"verdict":"FAIL"}') is None


def test_terminal_resume_rebuilds_missing_report_with_no_auditor(tmp_path: Path, monkeypatch) -> None:
    factory = _factory()
    run_dir = tmp_path / "report-recovery"
    run_dir.mkdir()
    policy = factory.load_document(factory.POLICY_PATH)
    state = {"run_schema": "ioabench.v5.overnight-s1/1", "run_id": "report-recovery",
             "policy_sha256": factory.canonical_sha256(policy), "status": "BLOCKED_INDEPENDENT_REVIEW",
             "started_utc": "2026-10-12T00:00:00Z", "last_substantive_progress_utc": "2026-10-12T00:05:00Z",
             "provider_operations": 9, "candidate_count": 1}
    factory._atomic_json(run_dir / "RUN_STATE.json", state)
    factory._atomic_json(run_dir / "MODEL_CATALOG.json", {"entry_count": 419})
    factory._atomic_json(run_dir / "candidate-01.json", {
        "candidate_no": 1, "status": "BLOCKED_INDEPENDENT_REVIEW",
        "generator": {"requested_model_id": "gemini-3.8-flash", "resolved_model_id": "gemini-3.8-flash"},
        "independent_auditor": None, "family_classification": {"status": "new_family"},
        "audit_gateway_errors": [{"model_id": "glm-5.3-flash", "error_type": "ProviderTransientError",
                                   "error": "empty response"}]})
    factory._atomic_text(run_dir / "EXECUTION_LOG.jsonl", "")
    monkeypatch.setattr(factory, "RUNS_ROOT", tmp_path)

    assert asyncio.run(factory._execute(run_dir, "report-recovery", 1, True, stop_on_failure=False)) == "BLOCKED_INDEPENDENT_REVIEW"
    report = (run_dir / "MORNING_REPORT.md").read_text(encoding="utf-8")
    assert "Independent auditor: n/a" in report
    assert "ProviderTransientError" in report
    assert "Workspace snapshot/version" in report
    assert "18-suite progress" in report
    assert "Next executable action" in report
    assert "Automatic continuation limitation" in report
    assert "Human Gate D: BLOCKED_EXTERNAL_REVIEW" in report
    assert "machine accepted 0; quality rejected 0; blocked/stopped 1" in report


def test_review_citations_must_resolve_to_supplied_candidate() -> None:
    factory = _factory()
    view = {"blueprint": {"suite_id": "T321"}}
    review = {"construct_fit": {"evidence": ["/candidate/blueprint/suite_id"]}}
    assert factory._review_citation_findings(review, view) == []
    review["construct_fit"]["evidence"] = ["/candidate/hidden_ground_truth"]
    assert factory._review_citation_findings(review, view)[0]["code"] == "REVIEW_CITATION_UNRESOLVED"


def test_surface_only_signature_difference_is_not_a_new_executed_family() -> None:
    factory = _factory()
    control, _ = factory.t321_slice.generate(seed=11, families=3)[1]
    from dataclasses import replace

    renamed = replace(control, world={**dict(control.world), "org": "other words without titlecase",
                                      "policy": "A paraphrase of the same transfer rule."},
                      fingerprints=("broker-alpha", "another partner"))
    assert factory._slice_reference_overlaps(renamed)


def test_review_path_index_resolves_in_serialized_input_and_excludes_oracle():
    factory = _factory()
    control, risk = factory.t321_slice.generate(seed=11, families=3)[0]
    view = factory._review_view({"suite_payload": {"offer_profiles": {}}, "a/b~c": [1]}, control, risk)
    view["family_evidence"] = {"classification": {"status": "new_family"}}
    user = json.loads(factory._review_prompt(view)[1]["content"])
    contract = user["citation_contract"]
    assert "/candidate/blueprint/suite_payload/offer_profiles" in contract["examples"]
    assert "/candidate/paired_cases/1/world/delivery_schedule" in contract["examples"]
    assert "/candidate/blueprint/a~1b~0c/0" in contract["evidence_paths"]
    for path in [*contract["examples"], *contract["evidence_paths"]]:
        factory.resolve_pointer(user, path)
    assert not any("/oracle" in path for path in contract["evidence_paths"])


@pytest.mark.parametrize("pointer", ["/candidate/suite_payload/offer_profiles", "/paired_cases/0/world",
                                     "/family_evidence/classification", "/candidate/oracle",
                                     "/candidate/paired_cases/3", 17])
def test_wrong_roots_missing_private_and_out_of_range_review_citations_still_reject(pointer):
    factory = _factory()
    view = {"blueprint": {"suite_payload": {"offer_profiles": {}}}, "paired_cases": [{"world": {}}],
            "family_evidence": {"classification": {}}}
    review = {"construct_fit": {"evidence": [pointer]}}
    assert factory._review_citation_findings(review, view)[0]["code"] == "REVIEW_CITATION_UNRESOLVED"


@pytest.mark.parametrize("evidence", [None, "/candidate/blueprint/suite_id", 17])
def test_malformed_review_evidence_has_schema_failure_without_crashing(evidence):
    factory = _factory()
    review = mock_review()
    review["construct_fit"]["evidence"] = evidence
    assert any(item["code"] == "REVIEW_EVIDENCE_INVALID" for item in factory.validate_review(review))
    factory._review_citation_findings(review, {"blueprint": {"suite_id": "T321"}})


def test_issue_citation_must_resolve_but_issue_location_can_describe_missing_field():
    factory = _factory()
    view = {"blueprint": {"suite_id": "T321"}}
    issue = {"code": "MISSING", "field_path": "/candidate/blueprint/not_present",
             "reason": "missing field", "evidence": "/candidate/blueprint/suite_id"}
    assert factory._review_citation_findings({"issues": [issue]}, view) == []
    issue["evidence"] = "/candidate/blueprint/not_present"
    assert factory._review_citation_findings({"issues": [issue]}, view)[0]["field_path"] == "/issues/0/evidence"


def test_stop_policy_catalog_failure_is_terminal_and_resume_makes_no_call(tmp_path, monkeypatch):
    factory = _factory()
    calls = 0

    class Adapter:
        def __init__(self, **kwargs):
            assert kwargs["stop_on_provider_error"] is True

        async def discover_models(self):
            nonlocal calls
            calls += 1
            raise ProviderTransientError("catalog down")

    monkeypatch.setattr(factory, "AIHubMixAdapter", Adapter)
    monkeypatch.setattr(factory, "_load_api_key", lambda: "fixture-key")
    run_dir = tmp_path / "strict"
    with pytest.raises(factory.FactoryPaused, match="PAUSED_PROVIDER"):
        asyncio.run(factory._execute(run_dir, "strict", 3, False, stop_on_failure=True))
    assert asyncio.run(factory._execute(run_dir, "strict", 3, True, stop_on_failure=True)) == "PAUSED_PROVIDER"
    assert calls == 1
    assert (run_dir / "PAUSE_REASON.json").is_file()


@pytest.mark.parametrize("failure", ["api", "json", "truncated", "blueprint", "identity",
                                     "audit_api", "audit_citation", "audit_verdict"])
def test_stop_policy_never_switches_models_or_continues_candidates(tmp_path, monkeypatch, failure):
    factory = _factory()
    spec = importlib.util.spec_from_file_location("compiler_fixture", ROOT / "tests/v5/test_t321_dyna_compiler.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    blueprint = fixture._blueprint()
    catalog = [{"model_id": "claude-sonnet-5-5", "model_name": "Claude Sonnet 5.5", "developer_id": "Anthropic"},
               {"model_id": "glm-5.3-flash", "model_name": "GLM 5.3 Flash", "developer_id": "Zhipu"},
               {"model_id": "gemini-3.8-flash", "model_name": "Gemini 3.8 Flash", "developer_id": "Google"}]
    requests = []

    class Adapter:
        base_url = "https://test.invalid/v1"

        def __init__(self, **kwargs):
            assert kwargs["stop_on_provider_error"] is True

        async def discover_models(self):
            return catalog

        async def resolve(self, model_id):
            return ModelProfile("aihubmix", model_id, {}, {})

        async def describe_model(self, model_id):
            return {"model_id": model_id, "protocols": ["openai.chat_completions"],
                "specs": {"max_output_tokens": 131072}, "domains": [{"capabilities": [
                    {"key": "reasoning-effort", "protocols": [{"protocol": "openai.chat_completions",
                        "fields": [{"name": "reasoning_effort", "enum": ["high"], "default": "high"}]}]},
                    {"key": "output-limit", "protocols": [{"protocol": "openai.chat_completions",
                        "fields": [{"name": "max_completion_tokens"}]}]}]}]}

        async def generate(self, profile, request):
            requests.append(profile.model_id)
            generator = profile.role == "GENERATOR"
            if (generator and failure == "api") or (not generator and failure == "audit_api"):
                raise ProviderTransientError("channel down")
            value = blueprint if generator else mock_review()
            if generator and failure == "blueprint":
                value["task_graph"][0]["tool"] = "unimplemented_payment"
            if not generator:
                for dimension in factory.REVIEW_DIMENSIONS:
                    value[dimension]["evidence"] = ["/candidate/blueprint/suite_id"]
                if failure == "audit_citation":
                    value["construct_fit"]["evidence"] = ["/candidate/suite_payload"]
                if failure == "audit_verdict":
                    value["semantic_consistency"]["score"] = 3
            model = "gemini-3.8-flash" if generator and failure == "identity" else profile.model_id
            return ModelResponse(text="not JSON" if generator and failure == "json" else json.dumps(value),
                                 model_id=profile.model_id,
                                 finish_reason="length" if generator and failure == "truncated" else "stop",
                                 provider_metadata={"model": model, "transport_metadata": {"x-aihubmix-model": model}})

    monkeypatch.setattr(factory, "AIHubMixAdapter", Adapter)
    monkeypatch.setattr(factory, "_load_api_key", lambda: "fixture-key")
    monkeypatch.setattr(factory, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(factory, "REGISTRY_PATH", tmp_path / "families.jsonl")
    monkeypatch.setattr(factory, "_baseline_overlaps", lambda _: [])
    monkeypatch.setattr(factory, "_slice_reference_overlaps", lambda _: [])
    run_dir = tmp_path / "strict"
    with pytest.raises(factory.FactoryPaused):
        asyncio.run(factory._execute(run_dir, "strict", 3, False, stop_on_failure=True,
                                    generator_model="claude-sonnet-5-5", auditor_model="glm-5.3-flash"))
    assert requests == (["claude-sonnet-5-5", "glm-5.3-flash"] if failure.startswith("audit_")
                        else ["claude-sonnet-5-5"])
    assert not (run_dir / "candidate-02.json").exists()
    assert not factory.REGISTRY_PATH.exists()
    state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
    assert state["status"].startswith("PAUSED_")
    assert asyncio.run(factory._execute(run_dir, "strict", 3, True, stop_on_failure=True,
                                       generator_model="claude-sonnet-5-5", auditor_model="glm-5.3-flash")) == state["status"]
    assert len(requests) == (2 if failure.startswith("audit_") else 1)
