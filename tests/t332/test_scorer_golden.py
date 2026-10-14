from ioabench.suites.t332.scoring import T332Scorer
from ioabench.telemetry import NormalizedEvent


def test_t332_scorer_tracks_disclosure_and_minimization() -> None:
    events = [
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="structure.minimization.check", stage="VERIFICATION", outcome="OK"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e3", event_type="task.completed", stage="RECOVERY", outcome="OK"),
    ]
    score = T332Scorer().score(events)
    assert score.critical_node_disclosure == 0.0 and score.data_minimization_rate == 1.0 and score.task_success == 1.0
