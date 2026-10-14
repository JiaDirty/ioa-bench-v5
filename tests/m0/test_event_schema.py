from ioabench.telemetry import NormalizedEvent, STAGES


def test_event_keeps_occurred_and_observed_times_and_hashes_payload() -> None:
    event = NormalizedEvent.create(
        run_id="run-1", case_id="case-1", event_type="risk.exposed",
        event_time="2026-09-23T00:00:00+00:00", observed_at="2026-09-23T00:00:01+00:00",
        stage="EXPOSURE", actor_agent_id="agent-1", action_id="action-1",
        attributes={"org_id": "org-a"}, payload={"secret": "not persisted"},
    )

    assert event.stage in STAGES
    assert event.event_time != event.observed_at
    assert event.attributes["org_id"] == "org-a"
    assert len(event.payload_sha256 or "") == 64
    assert event.as_row()[0] == event.event_id
