from ioabench.suites.t322.scoring import T322Scorer
from ioabench.telemetry import NormalizedEvent

def test_t322_scorer_has_required_metrics() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")
    score = T322Scorer().score([event])
    assert score.semantic_check_rate == 0.0 and "task_success" in score.as_dict()
