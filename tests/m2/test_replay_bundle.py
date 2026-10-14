from ioabench.replay import ReplayBundleBuilder
from ioabench.telemetry import NormalizedEvent


def test_replay_rebuilds_multi_hop_timeline_without_oracle_leakage() -> None:
    builder = ReplayBundleBuilder("run-1", "case-1")
    builder.add_events([
        NormalizedEvent.create(
            run_id="run-1", case_id="case-1", event_type="tool.call.result",
            event_time="2026-09-23T00:00:03+00:00", action_id="action-1",
            attributes={"oracle": {"truth": "unsafe"}, "result": "ok"},
        ),
        NormalizedEvent.create(
            run_id="run-1", case_id="case-1", event_type="agent.message.sent",
            event_time="2026-09-23T00:00:01+00:00", message_id="message-1",
            delegation_id="delegation-1", actor_agent_id="agent-a", target_agent_id="agent-b",
        ),
        NormalizedEvent.create(
            run_id="run-1", case_id="case-1", event_type="model.response",
            event_time="2026-09-23T00:00:02+00:00", actor_agent_id="agent-b",
        ),
    ])
    builder.add_model_record({"record_id": "model-1", "agent_id": "agent-b", "response": "approve"})
    bundle = builder.build(
        scenario={"scenario_id": "s-1", "ground_truth": {"unsafe": True}},
        world_snapshot={"account": "synthetic"},
        agents=[{"agent_id": "agent-a", "role_id": "sender"}, {"agent_id": "agent-b", "role_id": "reviewer"}],
        oracle_refs=["oracle://case-1"],
        final_utility={"completed": True},
    )

    assert [item["event_type"] for item in bundle.timeline] == [
        "agent.message.sent", "model.response", "tool.call.result"
    ]
    rebuilt = bundle.scorer_rebuild_inputs()
    assert rebuilt["message_ids"] == ["message-1"]
    assert rebuilt["delegation_ids"] == ["delegation-1"]
    assert rebuilt["action_ids"] == ["action-1"]
    assert "ground_truth" not in str(bundle.tested_agent_view()).casefold()
    assert "oracle" not in str(bundle.tested_agent_view()).casefold()


def test_replay_rejects_cross_case_events() -> None:
    builder = ReplayBundleBuilder("run-1", "case-1")
    event = NormalizedEvent.create(run_id="run-1", case_id="case-2", event_type="risk.exposed")
    try:
        builder.add_event(event)
    except ValueError as error:
        assert "another run or case" in str(error)
    else:
        raise AssertionError("cross-case event was accepted")
