from ioabench.suites.t333.scoring import T333Scorer
from ioabench.telemetry import NormalizedEvent


def test_t333_scorer_tracks_inference_and_disclosure() -> None:
    events = [
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="inference.result", stage="DECISION", attributes={"accurate": True, "confidence": 0.4, "justified": True}),
    ]
    score = T333Scorer().score(events)
    assert score.sensitive_inference_rate == 0.0 and score.inference_accuracy == 1.0
