from ioabench.suites.t313.scoring import T313Scorer
from ioabench.telemetry import NormalizedEvent

def test_t313_scorer_has_required_metrics() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")
    score = T313Scorer().score([event])
    assert score.boundary_check_rate == 0.0 and "task_success" in score.as_dict()
