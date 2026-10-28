import importlib.util
from pathlib import Path

import pytest

from ioabench.errors import ModelUnsupportedError
from ioabench.v5.ai_generation.model_routing import USER_CANDIDATES, auxiliary_parameters


def schema():
    return {"model_id": "qwen3.8-flash", "vendor": "alibaba", "protocols": ["openai.chat_completions"],
        "specs": {"context_window": 1000000, "max_output_tokens": 131072,
                  "reasoning_options": [{"type": "effort", "default": "xhigh"}]},
        "domains": [{"capabilities": [{"key": key, "protocols": [{"protocol": "openai.chat_completions", "fields": fields}]}
            for key, fields in [("output-limit", [{"name": "max_completion_tokens"}]),
                                ("reasoning-effort", [{"name": "reasoning_effort", "default": "medium", "enum": ["low", "medium", "xhigh"]}])]]}]}


def test_model_default_wins_over_generic_protocol_default_and_budget_is_explicit():
    s = schema()
    assert auxiliary_parameters(s) == {"max_completion_tokens": 131072, "reasoning_effort": "xhigh"}
    assert auxiliary_parameters(s, output_budget=16384) == {"max_completion_tokens": 16384, "reasoning_effort": "xhigh"}
    assert s["specs"]["max_output_tokens"] == 131072
    for invalid in (0, -1, True, 200000, "16384"):
        with pytest.raises(ModelUnsupportedError):
            auxiliary_parameters(s, output_budget=invalid)


def test_current_roster_is_exact_and_deepseek_revision_is_never_an_alias():
    assert len(USER_CANDIDATES) == len(set(USER_CANDIDATES)) == 8
    assert "qwen3.8-flash" in USER_CANDIDATES and "Qwen3.8-Flash-Next" not in USER_CANDIDATES
    assert "deepseek-v4.1-flash-1017" in USER_CANDIDATES and "deepseek-v4.1-flash" not in USER_CANDIDATES


def test_catalog_numeric_limit_requires_schema_and_cannot_increase_schema_ceiling():
    s = schema()
    assert auxiliary_parameters(s, catalog_entry={"max_output": 999999})["max_completion_tokens"] == 131072
    s["specs"].pop("max_output_tokens")
    assert auxiliary_parameters(s, catalog_entry={"max_output": 384000})["max_completion_tokens"] == 384000
    with pytest.raises(ModelUnsupportedError):
        auxiliary_parameters(None, catalog_entry={"max_output": 384000})


def test_fair_comparison_targets_are_fixed_supported_factors_and_not_display_renames():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/compare_auxiliary_models.py"
    spec = importlib.util.spec_from_file_location("comparison", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.TARGETS) == {"T321", "T331", "T352"}
    assert all(len(rows) == 4 for rows in module.TARGETS.values())
    assert len({tuple(sorted(row.items())) for row in module.TARGETS["T331"]}) == 4


def comparison_module():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/compare_auxiliary_models.py"
    spec = importlib.util.spec_from_file_location("comparison_checks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_candidate_reference_replay_and_tamper_detection(tmp_path):
    import hashlib
    from ioabench.v5.ai_generation.acquisition import program_proposal
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.evaluation import atomic_json
    module = comparison_module()
    task = {"id": "t331-replay-fixture", "suite": "T331", "seed": 27101, "target": module.TARGETS["T331"][0]}
    blueprint = program_proposal(suite_spec("T331", typed=True), seed=27101, difficulty="M", target=task["target"])
    assert module.validate_candidate(tmp_path, task, blueprint)["status"] == "ENGINEERING_VALID"
    name = "BLUEPRINT.json"
    atomic_json(tmp_path / "RESULT.json", {"status": "ENGINEERING_VALID", "evidence_sha256": {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()}})
    assert module.checked_result(tmp_path / "RESULT.json")["status"] == "ENGINEERING_VALID"
    (tmp_path / name).write_text("forged")
    with pytest.raises(ValueError, match="evidence changed"):
        module.checked_result(tmp_path / "RESULT.json")


def test_queued_generation_stops_before_model_call_after_auth_failure(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    module = comparison_module()
    from ioabench.v5.evaluation import atomic_json
    atomic_json(tmp_path / "MODEL_CATALOG.json", [])
    monkeypatch.setattr(module, "contract_for", lambda *a, **k: SimpleNamespace(
        profile=SimpleNamespace(role="GENERATOR"), parameters={"max_completion_tokens": 16384}))
    class NeverCalled:
        def __init__(self, *a, **k):
            pass
        async def invoke(self, *a, **k):
            pytest.fail("credential stop must prevent queued paid calls")
    monkeypatch.setattr(module, "AuxiliaryRouter", NeverCalled)
    async def execute():
        stop = asyncio.Event()
        stop.set()
        return await module.generate_task(tmp_path / "study", tmp_path, "test-model",
            {"id": "t331-auth-stop", "suite": "T331", "seed": 27101,
             "difficulty": "M", "target": module.TARGETS["T331"][0]},
            None, "openai.chat_completions", asyncio.Semaphore(1), stop)
    row = asyncio.run(execute())
    assert row["category"] == "AUTH/PERMISSION"
    assert row["status"] == "PROVIDER_FAILED"


def test_fixed_repair_inputs_are_rejected_and_originals_remain_valid():
    from copy import deepcopy
    path = Path(__file__).resolve().parents[2] / "scripts/v5/compare_auxiliary_repairs.py"
    spec = importlib.util.spec_from_file_location("fixed_repairs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tasks = module.repair_tasks()
    assert len(tasks) == 3
    for task in tasks:
        adapter = module.suite_spec(task["suite"], typed=True).adapter
        assert list(adapter.validate_blueprint(task["invalid_blueprint"]))
        repaired = deepcopy(task["invalid_blueprint"])
        repaired["suite_payload"][task["field"]] = {"T321": 2, "T331": 2, "T352": 5}[task["suite"]]
        assert not list(adapter.validate_blueprint(repaired))


def test_windows_progress_sharing_error_cannot_cancel_paid_tasks(tmp_path, monkeypatch):
    module = comparison_module()
    def locked(*args):
        raise PermissionError("Windows reader denied replace")
    monkeypatch.setattr(module, "atomic_json", locked)
    assert module.write_progress(tmp_path / "progress.json", {"completed": 1}) is False


def test_interrupted_comparison_settlement_never_constructs_provider(tmp_path, monkeypatch):
    module = comparison_module()
    from ioabench.v5.evaluation import atomic_json
    from ioabench.hashing import canonical_sha256
    tasks = [{"id": "retained"}, {"id": "unknown"}, {"id": "not-started"}]
    plan = {"models": ["model"], "tasks": tasks}
    atomic_json(tmp_path / "PREREGISTRATION.json", plan)
    atomic_json(tmp_path / "COMPARISON_EXECUTION_BINDING.json", {
        "preregistration_sha256": canonical_sha256(plan), "runtime_source_sha256": module.source_tree_hash(module.ROOT)})
    atomic_json(tmp_path / "generation/model/retained/RESULT.json", {
        "model_id": "model", "task": tasks[0], "status": "ENGINEERING_VALID"})
    atomic_json(tmp_path / "generation/model/unknown/model_io/first/attempt-001.json", {"status": "REQUEST_STARTED"})
    monkeypatch.setattr(module, "AIHubMixAdapter", lambda *a, **k: pytest.fail("offline settlement must not create a Provider"))
    report = module.settle(tmp_path)
    assert [row["status"] for row in report["rows"]] == ["ENGINEERING_VALID", "REQUEST_UNRESOLVED", "NOT_RUN"]
    assert report["provider_calls_this_settlement"] == 0
