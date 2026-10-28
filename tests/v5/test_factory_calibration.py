from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import sys

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract, AuxiliaryRouter
from ioabench.v5.evaluation import atomic_json


def calibration_script():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/calibrate_factory_candidates.py"
    spec = importlib.util.spec_from_file_location("factory_calibration_test_command", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


def make_panel(output):
    """Real runners/router/journals, with scripted local responses and deliberate stops."""
    module = calibration_script()
    cases = [case for suite in ("T321", "T331", "T352")
             for case in suite_spec(suite).slice_module.generate(91)[0]]
    catalog = [{"model_id": ident, "developer_id": number,
                "pricing": {"input": 1, "output": 2}}
               for number, ident in enumerate(("fixture-a", "fixture-b"), 1)]
    contracts = [AuxiliaryContract(ModelProfile("aihubmix", entry["model_id"], {}, {}, role="CALIBRATOR"),
                    {"max_tokens": 8192}, entry, "local-preflight.json", ("CALIBRATOR",)) for entry in catalog]
    atomic_json(output / "CALIBRATION_CONTRACT.json", {
        "runtime_source_sha256": module.source_tree_hash(module.ROOT),
        "script_sha256": "retained-original-script-hash", "models": [asdict(item) for item in contracts],
        "selected_case_sha256": [case.content_sha256() for case in cases], "repetitions": 2})
    atomic_json(output / "PAIRS.json", [case.as_dict() for case in cases])
    _, expected = module.planned_panel(output)

    class ProcessStopped(BaseException):
        pass

    class LocalPort:
        stop_on_provider_error = True

        def __init__(self, policy, mode):
            self.policy, self.mode, self.calls = policy, mode, 0

        async def generate(self, profile, request):
            self.calls += 1
            if self.mode == "pending":
                raise ProcessStopped()
            if self.mode == "infra" and self.calls > 1:
                raise TimeoutError("fixture connection timed out")
            response = await self.policy.generate(profile, request)
            return replace(response, model_id=profile.model_id, provider_metadata={"model": profile.model_id},
                           usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

    rows = []
    for (ident, (case, _)), mode in zip(expected.items(), ("complete", "infra", "pending")):
        spec = suite_spec(case.suite_id)
        router = AuxiliaryRouter(LocalPort(spec.policies["witness"], mode), [contracts[0]], catalog,
                                 output / "episodes" / ident / "model_io")
        if mode == "pending":
            with pytest.raises(ProcessStopped):
                run_dynamic_case(output / "replay", case, spec.slice_module, module.PanelPort(router),
                                 contracts[0].profile, run_id=ident, parameters=contracts[0].parameters)
        else:
            row = run_dynamic_case(output / "replay", case, spec.slice_module, module.PanelPort(router),
                                   contracts[0].profile, run_id=ident, parameters=contracts[0].parameters)
            assert row["status"] == ("COMPLETED" if mode == "complete" else "INFRA_INTERRUPTED")
            atomic_json(output / "episodes" / ident / "RESULT.json", row)
            rows.append(row)
    return module, rows


def test_panel_report_keeps_safe_task_failure_recovery_and_abstention_separate():
    module = calibration_script()
    rows = [dict(suite_id="T331-DYNA", model_id="panel", arm="RISK", status="COMPLETED",
        scientifically_eligible=True, score={"safety": "SAFE", "utility": False},
        outcome={"legacy_class": "TASK_SAFE_BUT_FAILED"}),
        dict(suite_id="T331-DYNA", model_id="panel", arm="RISK", status="COMPLETED",
        scientifically_eligible=True, score={"safety": "UNSAFE_RECOVERED", "utility": True},
        outcome={"legacy_class": "LATE_RECOVERY"}),
        dict(suite_id="T331-DYNA", model_id="panel", arm="CONTROL", status="COMPLETED",
        scientifically_eligible=False, score=None, outcome={"legacy_class": "SCORER_ABSTAINED"})]
    result = module.panel_summary(rows)["T331-DYNA"]
    assert result["episodes"] == 3 and result["eligible"] == 2
    assert result["safe_behavior"] == 1 and result["utility_success"] == 1
    assert result["outcomes"] == {"TASK_SAFE_BUT_FAILED": 1, "LATE_RECOVERY": 1, "SCORER_ABSTAINED": 1}


def test_pair_selection_supports_other_constructs_and_rejects_incomplete_or_duplicate_suites():
    module = calibration_script()
    spec = suite_spec("T361", typed=True)
    pair = list(spec.adapter.compile_pair(program_proposal(spec, seed=91, difficulty="M"), seed=91))
    assert module.select_pairs(pair, ["T361"]) == pair
    for cases, suites in ((pair[:1], ["T361"]), (pair, ["T361", "T361"]), (pair, ["T999"])):
        with pytest.raises(ValueError, match="panel"):
            module.select_pairs(cases, suites)


@pytest.mark.parametrize("difficulty", ["E", "M", "H"])
def test_selection_preserves_declared_difficulty_without_using_behavior(difficulty):
    module = calibration_script()
    spec = suite_spec("T363", typed=True)
    pairs = [case for label in ("E", "M", "H") for case in spec.adapter.compile_pair(
        program_proposal(spec, seed=91, difficulty=label), seed=91)]
    selected = module.select_pairs(pairs, ["T363"], difficulty)
    assert len(selected) == 2 and {case.arm for case in selected} == {"CONTROL", "RISK"}
    assert all(case.difficulty == difficulty and case.simulation_only for case in selected)
    with pytest.raises(ValueError, match="panel"):
        module.select_pairs(selected, ["T363"], "UNKNOWN")


def test_interleaved_replay_is_explicitly_scoped_to_auxiliary_profile(tmp_path):
    spec = suite_spec("T331")
    control, _ = spec.slice_module.generate(91)[0]
    for role, expected in (("CALIBRATOR", True), ("TESTED", False)):
        class WithReasoning:
            def __init__(self):
                self.messages = []
            async def generate(self, profile, request):
                self.messages.extend(request.messages)
                response = await spec.policies["witness"].generate(profile, request)
                return replace(response, reasoning_content="probe reasoning",
                               reasoning_details=[{"type": "reasoning.text", "text": "probe"}],
                               provider_metadata={"output_items": [{"type": "reasoning", "id": "raw-reasoning"}],
                                   "content_blocks": [{"type": "thinking", "thinking": "probe", "signature": "signed"}]})
        port = WithReasoning()
        profile = ModelProfile("aihubmix", "auxiliary-probe", {"auxiliary_interleaved_replay": True}, {}, role=role)
        result = run_dynamic_case(tmp_path, control, spec.slice_module, port, profile,
                                  run_id="reasoning-" + role.lower(), parameters={})
        assert result["status"] == "COMPLETED"
        assistants = [message for message in port.messages if message["role"] == "assistant"]
        assert assistants
        assert all(("reasoning_content" in message) == expected for message in assistants)
        assert all(("reasoning_details" in message) == expected for message in assistants)
        assert all(("output_items" in message) == expected for message in assistants)
        assert all(("content_blocks" in message) == expected for message in assistants)


def test_offline_settlement_preserves_original_bytes_and_exact_denominators(tmp_path, monkeypatch):
    module, original = make_panel(tmp_path)
    retained = module.retained_panel_files(tmp_path)
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **kwargs: pytest.fail("offline settlement constructed Provider"))
    monkeypatch.setattr(module, "run_dynamic_case", lambda *args, **kwargs: pytest.fail("offline settlement executed episode"))
    report = module.settle_stopped_panel(tmp_path, "two bounded network failures; stopped by operator")
    assert module.retained_panel_files(tmp_path) == retained
    assert report["planned_episodes"] == report["episodes"] == 24
    assert report["retained_result_rows"] == 2 and report["attempted_episodes"] == 3
    assert report["completed_episodes"] == report["scored_episodes"] == 1
    assert report["statuses"] == {"COMPLETED": 1, "INFRA_INTERRUPTED": 1,
        "INTERRUPTED_WITH_PENDING_REQUEST": 1, "NOT_RUN": 21}
    assert report["completion_attempts"] == original[0]["model_calls"] + original[1]["model_calls"] + 2
    assert report["finished_attempts"] == report["completion_attempts"] - 1
    assert report["missing_usage_attempts"] == report["billing_unknown_attempts"] == 2
    assert report["usage"]["total_tokens"] == 15 * sum(row["model_calls"] for row in original)
    assert report["estimated_usd_known_subtotal"] > 0 and report["provider_calls"] == 0
    stopped = json.loads((tmp_path / "STOP_REPORT.json").read_text(encoding="utf-8"))
    assert stopped["original_script_sha256"] == "retained-original-script-hash"
    assert json.loads((tmp_path / "RESULTS.json").read_text(encoding="utf-8"))[:2] == original
    assert module.settle_stopped_panel(tmp_path, report["stop_reason"]) == report
    assert module.retained_panel_files(tmp_path) == retained
    with pytest.raises(ValueError, match="reason changed"):
        module.settle_stopped_panel(tmp_path, "new reason")


@pytest.mark.parametrize("mutation", ["original", "aggregate", "new_attempt"])
def test_settlement_resume_rejects_changed_or_added_evidence(tmp_path, mutation):
    module, rows = make_panel(tmp_path)
    module.settle_stopped_panel(tmp_path, "stopped")
    if mutation == "original":
        path = tmp_path / "episodes" / rows[0]["run_id"] / "RESULT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["model_id"] = "forged"
        atomic_json(path, value)
    elif mutation == "aggregate":
        (tmp_path / "RESULTS.json").write_text("[]", encoding="utf-8")
    else:
        path = tmp_path / "episodes" / rows[0]["run_id"] / "model_io/call-extra/attempt-001.json"
        atomic_json(path, {"status": "REQUEST_STARTED"})
    with pytest.raises(ValueError, match="changed"):
        module.settle_stopped_panel(tmp_path, "stopped")


def test_offline_cli_needs_no_online_arguments_and_never_constructs_provider(tmp_path, monkeypatch, capsys):
    module, _ = make_panel(tmp_path)
    import ioabench.models
    monkeypatch.setattr(ioabench.models, "AIHubMixAdapter", lambda **kwargs: pytest.fail("CLI constructed Provider"))
    monkeypatch.setattr(sys, "argv", [str(module.__file__), "--out", str(tmp_path),
                                    "--settle-stopped", "--reason", "offline CLI stop"])
    runpy.run_path(module.__file__, run_name="__main__")
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "EXPLORATORY_PANEL_STOPPED" and printed["episodes"] == 24


def current_panel(output, monkeypatch, *, stop=False):
    """Exercise the real calibration command, runner and durable router with no network."""
    module = calibration_script()
    spec = suite_spec("T321")
    pair = list(spec.slice_module.generate(91)[0])
    pairs, proof = output.parent / "input-pairs.json", output.parent / "tool-proof.json"
    atomic_json(pairs, [case.as_dict() for case in pair])
    atomic_json(proof, {"evidence_sha256": {}, "rows": [{"model_id": "fixture-a", "status": "TOOL_LOOP_PASS"}]})
    entry = {"model_id": "fixture-a", "developer_id": 1, "pricing": {"input": 1, "output": 2}}
    contract = AuxiliaryContract(ModelProfile("aihubmix", "fixture-a", {}, {}, role="CALIBRATOR"),
        {"max_tokens": 8192}, entry, "local-preflight.json", ("CALIBRATOR",))
    monkeypatch.setattr(module, "qualified_contracts", lambda *args, **kwargs: ([entry], [contract], "local-only"))
    monkeypatch.setattr(module, "_load_api_key", lambda: "nonsecret-test-placeholder")

    class ProcessStopped(BaseException):
        pass

    class LocalPort:
        stop_on_provider_error = True

        async def generate(self, profile, request):
            if stop:
                raise ProcessStopped()
            response = await spec.policies["witness"].generate(profile, request)
            return replace(response, model_id=profile.model_id, provider_metadata={"model": profile.model_id},
                           usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **kwargs: LocalPort())
    args = (output, pairs, output.parent / "preflight", proof, ["fixture-a"], 1, ("T321",), pair[0].difficulty)
    if stop:
        with pytest.raises(ProcessStopped):
            module.calibrate(*args)
        report = module.settle_stopped_panel(output, "deliberately interrupted test request")
    else:
        report = module.calibrate(*args)
    return module, args, report, contract


def file_snapshot(output):
    return {path.relative_to(output).as_posix(): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in output.rglob("*") if path.is_file()}


@pytest.mark.parametrize("stop", [False, True])
def test_current_contract_json_round_trip_resume_is_read_only_and_never_opens_provider(tmp_path, monkeypatch, stop):
    output = tmp_path / "panel"
    module, args, report, contract = current_panel(output, monkeypatch, stop=stop)
    stored = json.loads((output / "CALIBRATION_CONTRACT.json").read_text(encoding="utf-8"))
    assert stored["models"][0]["allowed_roles"] == ["CALIBRATOR"]
    assert asdict(contract)["allowed_roles"] == ("CALIBRATOR",)
    before = file_snapshot(output)
    monkeypatch.setattr(module, "_load_api_key", lambda: pytest.fail("terminal resume loaded secret"))
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **kwargs: pytest.fail("terminal resume constructed Provider"))
    monkeypatch.setattr(module, "run_dynamic_case", lambda *args, **kwargs: pytest.fail("terminal resume executed episode"))
    assert module.calibrate(*args) == report
    assert file_snapshot(output) == before
    if stop:
        assert report["statuses"] == {"INTERRUPTED_WITH_PENDING_REQUEST": 1, "NOT_RUN": 1}
        assert report["completion_attempts"] == 1 and report["finished_attempts"] == 0


@pytest.mark.parametrize("mutation", ["source", "parameters", "selection", "old_script", "old_version"])
def test_terminal_resume_rejects_changed_execution_contract_before_provider(tmp_path, monkeypatch, mutation):
    output = tmp_path / "panel"
    module, args, _, contract = current_panel(output, monkeypatch)
    before = file_snapshot(output)
    if mutation == "source":
        monkeypatch.setattr(module, "source_tree_hash", lambda root: "changed-source")
    elif mutation == "parameters":
        monkeypatch.setattr(module, "qualified_contracts", lambda *args, **kwargs:
            ([contract.entry], [replace(contract, parameters={"max_tokens": 1})], "local-only"))
    elif mutation == "selection":
        pair = suite_spec("T321").slice_module.generate(92)[0]
        atomic_json(args[1], [case.as_dict() for case in pair])
    else:
        path = output / "CALIBRATION_CONTRACT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["script_sha256" if mutation == "old_script" else "version"] = "previous-contract"
        atomic_json(path, value)
        before = file_snapshot(output)
    monkeypatch.setattr(module, "_load_api_key", lambda: pytest.fail("contract rejection loaded secret"))
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **kwargs: pytest.fail("contract rejection constructed Provider"))
    with pytest.raises(ValueError, match="source/panel/selection changed"):
        module.calibrate(*args)
    assert file_snapshot(output) == before


@pytest.mark.parametrize("mutation", ["report", "aggregate", "case", "request", "result", "missing_binding"])
def test_completed_resume_rejects_terminal_or_retained_evidence_tamper(tmp_path, monkeypatch, mutation):
    output = tmp_path / "panel"
    module, args, _, _ = current_panel(output, monkeypatch)
    paths = {"report": output / "CALIBRATION_REPORT.json", "aggregate": output / "RESULTS.json",
             "case": output / "PAIRS.json", "request": next(output.glob("episodes/*/model_io/*/REQUEST_BINDING.json")),
             "result": next(output.glob("episodes/*/RESULT.json")), "missing_binding": output / "COMPLETION_REPORT.json"}
    path = paths[mutation]
    if mutation == "missing_binding":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b"\n")
    before = file_snapshot(output)
    monkeypatch.setattr(module, "_load_api_key", lambda: pytest.fail("tamper rejection loaded secret"))
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda **kwargs: pytest.fail("tamper rejection constructed Provider"))
    with pytest.raises((ValueError, FileNotFoundError)):
        module.calibrate(*args)
    assert file_snapshot(output) == before
