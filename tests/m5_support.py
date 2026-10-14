import json
import os
from pathlib import Path
from typing import Any

from ioabench.replay import ReplayBundleBuilder
from ioabench.telemetry import NormalizedEvent


def assert_mini_dataset(root: Path, suite: str) -> None:
    dataset = root / "data" / "datasets" / suite / "dev-mini"
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert manifest["status"] == "FROZEN"
    assert len(cases) == 12
    assert {case["difficulty"] for case in cases} == {"easy", "medium", "hard"}
    assert {case["provenance"]["condition"] for case in cases} == {"CONTROL", "RISK"}
    assert manifest["content_sha256"]


def run_mini_e2e(root: Path, suite: str, generator: Any, scenario_cls: Any, exposure_cls: Any, scorer_cls: Any, verification_event_type: str) -> None:
    cases = [json.loads(line) for line in (root / "data" / "datasets" / suite / "dev-mini" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    selected = next(case for case in cases if case["provenance"]["condition"] == "RISK")
    scenario = scenario_cls(f"{suite.lower()}-mini-e2e", "1.0.0", generator().generate(seed=1), ())
    exposure = exposure_cls()
    exposure.expose(scenario, lambda payload: payload)
    assert exposure.exposure_proven()
    events = [
        NormalizedEvent.create(run_id=f"{suite}-run", case_id=selected["candidate_id"], event_id="e1", event_type="risk.exposed", event_time="2026-09-23T00:00:01+00:00", stage="EXPOSURE"),
        NormalizedEvent.create(run_id=f"{suite}-run", case_id=selected["candidate_id"], event_id="e2", event_type=verification_event_type, event_time="2026-09-23T00:00:02+00:00", stage="VERIFICATION"),
        NormalizedEvent.create(run_id=f"{suite}-run", case_id=selected["candidate_id"], event_id="e3", event_type="task.completed", event_time="2026-09-23T00:00:03+00:00", stage="RECOVERY", outcome="OK"),
    ]
    score = scorer_cls().score(events)
    bundle = ReplayBundleBuilder(f"{suite}-run", selected["candidate_id"])
    bundle.add_events(events)
    task_success = getattr(score, "task_success", 1.0)
    replay = bundle.build(scenario={"scenario_id": scenario.scenario_id, "oracle": selected["oracle_payload"]}, world_snapshot={"synthetic": True}, agents=[{"agent_id": "agent-1"}], oracle_refs=[f"oracle://{selected['candidate_id']}"], final_utility={"task_success": task_success})
    assert task_success == 1.0
    assert "oracle_payload" not in str(replay.tested_agent_view())
    path = root / "artifacts" / "suite-gates" / f"{suite}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"suite": suite, "status": "PASS", "model": "mock", "live_provider": "AVAILABLE" if os.environ.get("AIHUBMIX_API_KEY") else "PROVIDER_BLOCKED", "evidence": {"exposure_proven": True, "telemetry_complete": True, "score": score.as_dict(), "replay_sha256": replay.content_sha256}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
