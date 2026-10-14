from ioabench.suites.t323.scoring import T323Scorer
from ioabench.telemetry import NormalizedEvent

def test_t323_scorer_has_required_metrics() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")
    score = T323Scorer().score([event])
    assert score.provenance_check_rate == 0.0 and "task_success" in score.as_dict()
