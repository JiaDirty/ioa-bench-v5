from ioabench.runtime.offline_run import telemetry_complete
from ioabench.telemetry import NormalizedEvent


def test_exposure_messages_are_telemetry_complete() -> None:
    events = [
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="agent.message.received", stage="EXPOSURE"),
    ]
    assert telemetry_complete(events)
