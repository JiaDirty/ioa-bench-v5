import json
import os
from pathlib import Path

from ioabench.replay import ReplayBundleBuilder
from ioabench.suites.t312.generation import T312Generator
from ioabench.suites.t312.scenario import T312ExposureController, T312Scenario
from ioabench.suites.t312.scoring import T312Scorer
from ioabench.telemetry import NormalizedEvent


def test_t312_mock_e2e_scores_and_replays_mini_case() -> None:
    root = Path(__file__).parents[2]
    cases = [json.loads(line) for line in (root / "data" / "datasets" / "T312" / "dev-mini" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
    selected = next(case for case in cases if case["provenance"]["condition"] == "RISK")
    scenario = T312Scenario("t312-mini-e2e", "1.0.0", T312Generator().generate(seed=1), ())
    exposure = T312ExposureController()
    received = []
    exposure.expose(scenario, received.append)
    assert received and exposure.exposure_proven()

    def event(event_id: str, event_type: str, stage: str, **fields: str) -> NormalizedEvent:
        return NormalizedEvent.create(
            run_id="t312-run", case_id=selected["candidate_id"], event_id=event_id,
            event_type=event_type, event_time=f"2026-09-23T00:00:0{event_id[-1]}+00:00", stage=stage, **fields,
        )

    events = [
        event("e1", "risk.exposed", "EXPOSURE"),
        event("e2", "model.input", "EXPOSURE", actor_agent_id="agent-1"),
        event("e3", "registry.crosscheck", "VERIFICATION", actor_agent_id="agent-1"),
        event("e4", "task.completed", "RECOVERY", actor_agent_id="agent-1", outcome="OK"),
    ]
    score = T312Scorer().score(events)
    replay = ReplayBundleBuilder("t312-run", selected["candidate_id"])
    replay.add_events(events)
    bundle = replay.build(
        scenario={"scenario_id": scenario.scenario_id, "oracle": selected["oracle_payload"]},
        world_snapshot={"registry": "synthetic"},
        agents=[{"agent_id": "agent-1", "org_id": "org-a"}],
        oracle_refs=[f"oracle://{selected['candidate_id']}"],
        final_utility={"task_success": score.task_success},
    )
    assert score.task_success == 1.0
    assert score.registry_crosscheck_rate == 1.0
    assert bundle.scorer_rebuild_inputs()["action_ids"] == []
    assert "oracle_payload" not in str(bundle.tested_agent_view())

    artifact_path = root / "artifacts" / "suite-gates" / "T312.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps({
        "suite": "T312", "status": "PASS", "model": "mock", "live_provider": "AVAILABLE" if os.environ.get("AIHUBMIX_API_KEY") else "PROVIDER_BLOCKED",
        "evidence": {"exposure_proven": True, "telemetry_complete": True, "score": score.as_dict(), "replay_sha256": bundle.content_sha256},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
