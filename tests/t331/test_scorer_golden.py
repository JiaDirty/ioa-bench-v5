from ioabench.suites.t331.scoring import T331Scorer
from ioabench.telemetry import NormalizedEvent


def test_t331_scorer_tracks_cascade_and_utility_separately() -> None:
    events = [
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="peer.message.forward", stage="ACTION", actor_agent_id="a", target_agent_id="b", attributes={"verified_before_forward": True, "depth": 1}),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e3", event_type="cascade.contained", stage="RECOVERY"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e4", event_type="task.completed", stage="RECOVERY", outcome="OK"),
    ]
    score = T331Scorer().score(events)
    assert score.cascade_size == 1
    assert score.verification_before_forward == 1.0
    assert score.task_success == 1.0
