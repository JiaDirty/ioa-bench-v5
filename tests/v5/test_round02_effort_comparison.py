"""Quality failures remain failures and cannot confer auditor qualification."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys

import pytest


def module():
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("round02_efforts", scripts / "compare_round02_efforts.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("correct", [True, False])
def test_same_task_diagnostic_quality_and_resume(tmp_path, correct):
    mod = module()
    calls = []
    task = {"id": "evidence-contradiction", "prompt": "Which revision?", "expected": {"revision": 7}}
    class Study:
        out = tmp_path
        async def invoke(self, config, directory, request_id, messages):
            calls.append((config, messages))
            return type("Response", (), {"text": json.dumps({"revision": 7 if correct else 4})})()
    config = {"id": "model--high", "model": "model", "parameters": {"max_output_tokens": 4096}}
    first = asyncio.run(mod.quality(Study(), config, task))
    before = (tmp_path / "quality/model--high/evidence-contradiction/RESULT.json").read_bytes()
    assert asyncio.run(mod.quality(Study(), config, task)) == first
    assert first["status"] == ("PASS" if correct else "FAIL")
    assert first["machine_qualified"] is False and len(calls) == 1
    assert calls[0][0]["parameters"]["max_output_tokens"] == 16384
    assert (tmp_path / "quality/model--high/evidence-contradiction/RESULT.json").read_bytes() == before


def test_no_effort_plan_before_a_verified_protocol(tmp_path):
    mod = module()
    (tmp_path / "PROTOCOL_PLAN.json").write_text(json.dumps({"configs": [
        {"id": "failed-model", "model": "failed"}, {"id": "not-run", "model": "not-run"}]}))
    result = tmp_path / "protocols/failed-model/p1/RESULT.json"
    result.parent.mkdir(parents=True)
    result.write_text(json.dumps({"status": "FAIL"}))
    plan = mod.prepare(tmp_path)
    assert plan["configs"] == [] and len(plan["tasks"]) == 8
    assert {task.get("suite") for task in plan["tasks"] if "suite" in task} == {"T321", "T331", "T352"}
    assert plan["auditor_qualified"] is plan["formal_production"] is False
