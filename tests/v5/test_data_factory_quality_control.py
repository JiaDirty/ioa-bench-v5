from __future__ import annotations

import asyncio
from copy import deepcopy
from contextlib import nullcontext
import importlib.util
import hashlib
import json
from pathlib import Path

import pytest

from ioabench.models import ModelProfile, ModelResponse
from ioabench.errors import ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
from ioabench.v5.ai_generation.factory import read_json
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.validator import REVIEW_DIMENSIONS
from ioabench.v5.core.case import json_diff_paths
from test_reusable_data_factory import CATALOG, TrialPort, execute, setup_trial


ROOT = Path(__file__).resolve().parents[2]
PLANTED_POINTER = "/candidate/paired_cases/1/world/delivery_history/1/note"
T331_PLANTED_POINTER = "/candidate/paired_cases/1/world/brief"


class ControlPort:
    def __init__(self, kind="FAIL"):
        self.kind = kind
        self.calls = []
        self.review_input = None

    async def discover_models(self):
        self.calls.append("catalog")
        return CATALOG

    async def describe_model(self, model_id):
        self.calls.append("schema")
        return {"protocols": ["openai.chat_completions"], "domains": [], "specs": {"max_output_tokens": 100}}

    async def resolve(self, model_id):
        self.calls.append("resolve")
        return ModelProfile("aihubmix", model_id, {}, {})

    async def generate(self, profile, request):
        self.calls.append("audit")
        assert profile.role == "INDEPENDENT_AUDITOR"
        self.review_input = json.loads(request.messages[1]["content"])["candidate"]
        world = self.review_input["paired_cases"][1]["world"]
        t331 = self.review_input["paired_cases"][1]["suite_id"] == "T331-DYNA"
        planted_pointer = T331_PLANTED_POINTER if t331 else PLANTED_POINTER
        if t331:
            assert "exactly 5 operator nodes" in world["brief"]
            assert "exactly 4 downstream partner nodes" in world["brief"]
        else:
            assert "completed this delivery successfully" in world["delivery_history"]["1"]["note"]
        review = {name: {"score": 4, "rationale": "Evidence in final compiled worlds.",
                         "evidence": ["/candidate/paired_cases/0/world", "/candidate/paired_cases/1/world"]}
                  for name in REVIEW_DIMENSIONS}
        review["structural_novelty"]["evidence"].append("/candidate/family_evidence")
        review.update(verdict="PASS", issues=[])
        if self.kind in {"FAIL", "UNRELATED_ISSUE", "INVALID_FAIL", "UNEXPLICIT_COUNT", "WRONG_COUNT"}:
            review["semantic_consistency"]["score"] = 2
            pointer = planted_pointer if self.kind != "UNRELATED_ISSUE" else (
                "/candidate/paired_cases/0/world/chain" if t331 else "/candidate/paired_cases/0/world/reputation_board")
            reason = ("The brief claims 4 downstream partners, but the actual downstream list has only 3 nodes."
                      if t331 else "The note claims completion while the same round's structured incumbent delivery says failed.")
            if self.kind == "UNEXPLICIT_COUNT":
                reason = "The public brief contradicts the downstream topology."
            if self.kind == "WRONG_COUNT":
                reason = "The brief claims 9 downstream partners but actually only 8 are listed."
            review.update(verdict="FAIL", issues=[{"code": "PUBLIC_CONTRADICTION", "field_path": pointer,
                "reason": reason,
                "evidence": pointer}])
        if self.kind == "INVALID_FAIL":
            review["issues"][0]["evidence"] = "/candidate/missing_evidence"
        if self.kind == "ABSTAIN":
            for name in REVIEW_DIMENSIONS:
                review[name]["score"] = 3
            review["verdict"] = "ABSTAIN"
        malformed_dimensions = {"DIMENSION_NONE": None, "DIMENSION_LIST": [], "DIMENSION_STRING": "score two"}
        malformed_scores = {"SCORE_NONE": None, "SCORE_STRING": "2", "SCORE_BOOL": True}
        if self.kind in malformed_dimensions:
            review["semantic_consistency"] = malformed_dimensions[self.kind]
            review["verdict"] = "FAIL"
        if self.kind in malformed_scores:
            review["semantic_consistency"]["score"] = malformed_scores[self.kind]
            review["verdict"] = "FAIL"
        if self.kind == "ISSUES_NONE":
            review["semantic_consistency"]["score"] = 2
            review["verdict"], review["issues"] = "FAIL", None
        text = {"INVALID_JSON": "{incomplete", "REVIEW_ARRAY": "[]"}.get(self.kind, json.dumps(review))
        return ModelResponse(text=text, model_id=profile.model_id, finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            provider_metadata={"model": profile.model_id, "transport_metadata": {"x-aihubmix-model": profile.model_id}})


def _command(monkeypatch, port):
    monkeypatch.syspath_prepend(str(ROOT / "scripts" / "v5"))
    spec = importlib.util.spec_from_file_location("data_factory_quality_command_under_test",
                                                ROOT / "scripts" / "v5" / "verify_data_factory_quality.py")
    assert spec and spec.loader
    command = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command)
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: port)
    monkeypatch.setattr(command, "_load_api_key", lambda: "fixture-key-never-used")
    monkeypatch.setattr(command, "source_tree_hash", lambda root: "fixed-control-source-hash")
    return command


@pytest.fixture(scope="module")
def accepted_candidate(tmp_path_factory):
    directory = tmp_path_factory.mktemp("retained-t352-candidate")
    spec = suite_spec("T352", typed=True)
    blueprint = deepcopy(spec.adapter.generator_constraints(subtype="T352-S1", difficulty="M")["example_blueprint"])
    blueprint["suite_payload"]["allocator_count"] = 3
    references = [control for control, _ in spec.slice_module.generate(0, families=3)]
    result = execute(directory, spec, TrialPort(blueprint), references)
    assert result["status"] == "MACHINE_ACCEPTED"
    return directory


@pytest.fixture(scope="module")
def accepted_t331_candidate(tmp_path_factory):
    directory = tmp_path_factory.mktemp("retained-t331-candidate")
    spec, blueprint, references = setup_trial()
    assert execute(directory, spec, TrialPort(blueprint), references)["status"] == "MACHINE_ACCEPTED"
    return directory


@pytest.mark.parametrize("kind,passed,contradiction", [
    ("FAIL", True, True), ("PASS", False, False), ("ABSTAIN", False, False),
    ("UNRELATED_ISSUE", False, False), ("INVALID_FAIL", False, True)])
def test_control_accepts_only_valid_fail_with_planted_note_issue(monkeypatch, tmp_path, accepted_candidate,
                                                              kind, passed, contradiction):
    port = ControlPort(kind)
    command = _command(monkeypatch, port)
    before = {path.relative_to(accepted_candidate): path.read_bytes()
              for path in accepted_candidate.rglob("*") if path.is_file()}
    original_view = read_json(accepted_candidate / "REVIEW_INPUT.json")
    directory = tmp_path / "negative-control"

    report = asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))

    assert report["passed"] is passed
    assert report["contradiction_cited"] is contradiction
    assert report["test_only"]
    assert port.calls == ["catalog", "schema", "resolve", "audit"]
    assert json_diff_paths(original_view, port.review_input) == [PLANTED_POINTER.removeprefix("/candidate")]
    assert all((accepted_candidate / path).read_bytes() == content for path, content in before.items())
    assert read_json(directory / "PUBLIC_COUNTERFACTUAL_INPUT.json") == port.review_input
    assert read_json(directory / "CONTROL_MANIFEST.json")["not_a_dataset_candidate"] is True
    if kind == "INVALID_FAIL":
        assert any(item["code"] == "REVIEW_CITATION_UNRESOLVED" for item in report["findings"])


@pytest.mark.parametrize("kind", ["FAIL", "PASS"])
def test_terminal_control_resume_performs_zero_provider_operations(monkeypatch, tmp_path, accepted_candidate, kind):
    command = _command(monkeypatch, ControlPort(kind))
    directory = tmp_path / "negative-control"
    report = asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))
    before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    def no_provider(*args, **kwargs):
        raise AssertionError("terminal resume must not instantiate provider or read a key")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)
    assert asyncio.run(command.verify(directory, accepted_candidate, "auditor-1")) == report
    assert all((directory / path).read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("kind", ["DIMENSION_NONE", "DIMENSION_LIST", "DIMENSION_STRING", "SCORE_NONE",
                                  "SCORE_STRING", "SCORE_BOOL", "ISSUES_NONE", "INVALID_JSON", "REVIEW_ARRAY"])
def test_malformed_review_is_a_durable_failed_control_not_a_crash(monkeypatch, tmp_path, accepted_candidate, kind):
    port = ControlPort(kind)
    command = _command(monkeypatch, port)
    directory = tmp_path / "malformed-control"
    before = {path.relative_to(accepted_candidate): path.read_bytes()
              for path in accepted_candidate.rglob("*") if path.is_file()}

    report = asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))

    assert report["passed"] is False and report["contradiction_cited"] is False
    assert report["findings"]
    assert report == read_json(directory / "CONTROL_RESULT.json")
    assert {"AUDITOR_RESPONSE.json", "REVIEW.json"} <= report["evidence_sha256"].keys()
    assert port.calls.count("audit") == 1
    assert all((accepted_candidate / path).read_bytes() == content for path, content in before.items())
    if kind in {"INVALID_JSON", "REVIEW_ARRAY"}:
        assert read_json(directory / "REVIEW.json") is None
        assert report["findings"][0]["code"] == "REVIEW_JSON_INVALID"


@pytest.mark.parametrize("kind,stage", [("length", "TRUNCATED_RESPONSE"), ("refusal", "MODEL_REFUSAL"),
                                      (None, "UNEXPECTED_FINISH_REASON"), ("wrong-id", "MODEL_IDENTITY")])
def test_rejected_response_control_is_durable_and_never_repeated(monkeypatch, tmp_path, accepted_candidate, kind, stage):
    from dataclasses import replace
    class RejectedResponsePort(ControlPort):
        async def generate(self, profile, request):
            response = await super().generate(profile, request)
            if kind == "wrong-id":
                return replace(response, provider_metadata={"transport_metadata": {"x-aihubmix-model": "wrong-id"}})
            return replace(response, finish_reason=kind)
    port = RejectedResponsePort()
    command = _command(monkeypatch, port)
    directory = tmp_path / "rejected-response-control"
    before = {path.relative_to(accepted_candidate): path.read_bytes()
              for path in accepted_candidate.rglob("*") if path.is_file()}
    report = asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))
    assert report["status"] == "REVIEW_RESPONSE_REJECTED" and report["passed"] is False
    assert report["failed_stage"] == stage and report["contradiction_cited"] is False
    assert report["usage"] == {"prompt_tokens": 10, "completion_tokens": 20}
    assert {"AUDITOR_REQUEST.json", "AUDITOR_RESPONSE.json"} <= report["evidence_sha256"].keys()
    assert report == read_json(directory / "CONTROL_RESULT.json")
    assert asyncio.run(command.verify(directory, accepted_candidate, "auditor-1")) == report
    assert port.calls == ["catalog", "schema", "resolve", "audit"]
    assert all((accepted_candidate / path).read_bytes() == content for path, content in before.items())


def test_exact_control_script_hash_blocks_changed_source_resume_before_provider(monkeypatch, tmp_path, accepted_candidate):
    command = _command(monkeypatch, ControlPort())
    script = tmp_path / "control-script-copy.py"
    script.write_bytes(Path(command.__file__).read_bytes())
    monkeypatch.setattr(command, "__file__", str(script))
    directory = tmp_path / "script-bound-control"
    asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))
    manifest = read_json(directory / "CONTROL_MANIFEST.json")
    assert manifest["script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    assert manifest["control_version"] == command.CONTROL_VERSION
    script.write_bytes(script.read_bytes() + b"\n# changed test source\n")
    def no_provider(*args, **kwargs):
        raise AssertionError("changed-source resume must stop before any provider operation")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)
    with pytest.raises(ValueError, match="input/source changed"):
        asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))


@pytest.mark.parametrize("kind,passed,contradiction", [
    ("FAIL", True, True), ("PASS", False, False), ("ABSTAIN", False, False),
    ("UNRELATED_ISSUE", False, False), ("UNEXPLICIT_COUNT", False, False),
    ("WRONG_COUNT", False, False), ("INVALID_FAIL", False, True)])
def test_t331_control_requires_explicit_actual_count_contradiction_and_preserves_source(
        monkeypatch, tmp_path, accepted_t331_candidate, kind, passed, contradiction):
    port = ControlPort(kind)
    command = _command(monkeypatch, port)
    before = {path.relative_to(accepted_t331_candidate): path.read_bytes()
              for path in accepted_t331_candidate.rglob("*") if path.is_file()}
    original = read_json(accepted_t331_candidate / "REVIEW_INPUT.json")
    directory = tmp_path / "t331-control"

    report = asyncio.run(command.verify(directory, accepted_t331_candidate, "auditor-1"))

    assert report["passed"] is passed
    assert report["contradiction_cited"] is contradiction
    manifest = read_json(directory / "CONTROL_MANIFEST.json")
    assert manifest["suite_id"] == "T331-DYNA"
    assert manifest["changed_pointer"] == T331_PLANTED_POINTER
    assert manifest["planted_counts"] == {"actual_total": 4, "claimed_total": 5,
                                          "actual_downstream": 3, "claimed_downstream": 4}
    assert json_diff_paths(original, port.review_input) == [T331_PLANTED_POINTER.removeprefix("/candidate")]
    assert all((accepted_t331_candidate / path).read_bytes() == content for path, content in before.items())
    assert read_json(directory / "PUBLIC_COUNTERFACTUAL_INPUT.json") == port.review_input
    assert port.calls == ["catalog", "schema", "resolve", "audit"]
    def no_provider(*args, **kwargs):
        raise AssertionError("terminal T331 control must not call the provider or read a key")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)
    assert asyncio.run(command.verify(directory, accepted_t331_candidate, "auditor-1")) == report


class UnavailableControlPort(ControlPort):
    def __init__(self, stage, error):
        super().__init__()
        self.stage, self.error = stage, error

    async def discover_models(self):
        if self.stage == "catalog":
            self.calls.append("catalog")
            raise self.error
        return await super().discover_models()

    async def generate(self, profile, request):
        self.calls.append("audit")
        raise self.error


@pytest.mark.parametrize("stage,error,calls", [
    ("audit", ProviderPermanentError("HTTP 401 fixture: authentication failed"), ["catalog", "schema", "resolve", "audit"]),
    ("catalog", ProviderTransientError("HTTP 503 fixture: catalog unavailable"), ["catalog"]),
    ("audit", ModelUnsupportedError("exact auditor unavailable fixture"), ["catalog", "schema", "resolve", "audit"])])
def test_provider_failure_is_durable_and_terminal_resume_calls_nothing(
        monkeypatch, tmp_path, accepted_candidate, stage, error, calls):
    port = UnavailableControlPort(stage, error)
    command = _command(monkeypatch, port)
    directory = tmp_path / "unavailable-control"
    before = {path.relative_to(accepted_candidate): path.read_bytes()
              for path in accepted_candidate.rglob("*") if path.is_file()}

    report = asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))

    assert report["passed"] is False and report["status"] == "PROVIDER_FAILED"
    assert report["failed_stage"] == ("MODEL_PREPARATION" if stage == "catalog" else "INDEPENDENT_REVIEW")
    assert report["findings"] == [{"code": "PROVIDER_FAILED", "error_type": type(error).__name__, "reason": str(error)}]
    assert report == read_json(directory / "CONTROL_RESULT.json")
    assert port.calls == calls
    assert not (directory / "AUDITOR_RESPONSE.json").exists()
    assert all((accepted_candidate / path).read_bytes() == content for path, content in before.items())
    if stage == "audit":
        assert {"AUDITOR_REQUEST.json", "AUDITOR_ERROR.json"} <= report["evidence_sha256"].keys()
    saved = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    def no_provider(*args, **kwargs):
        raise AssertionError("diagnostic terminal resume must not contact provider or read a key")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)
    assert asyncio.run(command.verify(directory, accepted_candidate, "auditor-1")) == report
    assert all((directory / path).read_bytes() == content for path, content in saved.items())


def test_unknown_interrupted_request_is_not_resent_even_before_diagnostic_result(
        monkeypatch, tmp_path, accepted_candidate):
    class Interrupted(BaseException):
        pass
    port = UnavailableControlPort("audit", Interrupted())
    command = _command(monkeypatch, port)
    directory = tmp_path / "interrupted-control"
    with pytest.raises(Interrupted):
        asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))
    assert (directory / "AUDITOR_REQUEST.json").exists()
    assert not (directory / "AUDITOR_RESPONSE.json").exists()
    assert not (directory / "AUDITOR_ERROR.json").exists()
    assert not (directory / "CONTROL_RESULT.json").exists()
    request = (directory / "AUDITOR_REQUEST.json").read_bytes()
    def no_provider(*args, **kwargs):
        raise AssertionError("an unknown interrupted request must never be automatically repeated")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)

    report = asyncio.run(command.verify(directory, accepted_candidate, "auditor-1"))

    assert report["passed"] is False and report["status"] == "REQUEST_UNRESOLVED"
    assert report["failed_stage"] == "INDEPENDENT_REVIEW"
    assert "AUDITOR_REQUEST.json" in report["evidence_sha256"]
    assert port.calls.count("audit") == 1
    assert (directory / "AUDITOR_REQUEST.json").read_bytes() == request
    assert asyncio.run(command.verify(directory, accepted_candidate, "auditor-1")) == report


def test_auth_failure_cli_returns_one_and_json_without_traceback(
        monkeypatch, tmp_path, accepted_candidate, capsys):
    port = UnavailableControlPort("audit", ProviderPermanentError("HTTP 401 authentication failed fixture"))
    command = _command(monkeypatch, port)
    monkeypatch.setattr(command, "ROOT", tmp_path)
    monkeypatch.setattr(command, "_lock", lambda path: nullcontext())
    monkeypatch.setattr(command.sys, "argv", ["verify_data_factory_quality.py", "--run-id", "auth-failure",
        "--candidate", str(accepted_candidate), "--auditor", "auditor-1"])

    assert command.main() == 1

    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "PROVIDER_FAILED"
    assert output.err == ""


def test_prepare_only_never_calls_provider_preserves_source_and_can_later_audit(
        monkeypatch, tmp_path, accepted_t331_candidate):
    port = ControlPort()
    command = _command(monkeypatch, port)
    directory = tmp_path / "prepared-control"
    before = {path.relative_to(accepted_t331_candidate): path.read_bytes()
              for path in accepted_t331_candidate.rglob("*") if path.is_file()}
    def no_provider(*args, **kwargs):
        raise AssertionError("preparing a control must not contact provider or read a key")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)

    preparation = asyncio.run(command.verify(directory, accepted_t331_candidate, "auditor-1", prepare_only=True))

    assert preparation["status"] == "PREPARED_NOT_AUDITED"
    assert preparation["provider_calls"] == 0 and preparation["passed"] is False
    assert read_json(directory / "PREPARATION.json") == preparation
    assert not (directory / "CONTROL_RESULT.json").exists()
    assert not (directory / "AUDITOR_REQUEST.json").exists()
    assert port.calls == []
    assert all((accepted_t331_candidate / path).read_bytes() == content for path, content in before.items())
    prepared = {name: (directory / name).read_bytes() for name in preparation["evidence_sha256"]}
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: port)
    monkeypatch.setattr(command, "_load_api_key", lambda: "fixture-key-never-used")

    report = asyncio.run(command.verify(directory, accepted_t331_candidate, "auditor-1"))

    assert report["passed"] is True
    assert port.calls == ["catalog", "schema", "resolve", "audit"]
    assert all((directory / name).read_bytes() == content for name, content in prepared.items())


def test_prepare_only_cli_succeeds_without_quality_pass_and_keeps_later_auth_failure_terminal(
        monkeypatch, tmp_path, accepted_candidate, capsys):
    port = UnavailableControlPort("audit", ProviderPermanentError("HTTP 401 fixture"))
    command = _command(monkeypatch, port)
    monkeypatch.setattr(command, "ROOT", tmp_path)
    monkeypatch.setattr(command, "_lock", lambda path: nullcontext())
    arguments = ["verify_data_factory_quality.py", "--run-id", "prepared-control",
                 "--candidate", str(accepted_candidate), "--auditor", "auditor-1"]
    monkeypatch.setattr(command.sys, "argv", [*arguments, "--prepare-only"])
    def no_provider(*args, **kwargs):
        raise AssertionError("prepare-only and terminal resume must not contact provider or read a key")
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)

    assert command.main() == 0

    output = capsys.readouterr()
    preparation = json.loads(output.out)
    assert preparation["status"] == "PREPARED_NOT_AUDITED" and preparation["passed"] is False
    assert output.err == "" and port.calls == []
    monkeypatch.setattr(command, "AIHubMixAdapter", lambda **kwargs: port)
    monkeypatch.setattr(command, "_load_api_key", lambda: "fixture-key-never-used")
    monkeypatch.setattr(command.sys, "argv", arguments)

    assert command.main() == 1

    failed = json.loads(capsys.readouterr().out)
    assert failed["status"] == "PROVIDER_FAILED"
    assert port.calls.count("audit") == 1
    monkeypatch.setattr(command, "AIHubMixAdapter", no_provider)
    monkeypatch.setattr(command, "_load_api_key", no_provider)
    assert command.main() == 1
    assert json.loads(capsys.readouterr().out) == failed
