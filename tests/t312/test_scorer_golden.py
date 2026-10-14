from ioabench.suites.t312.scoring import T312Scorer
from ioabench.telemetry import NormalizedEvent


def test_t312_scorer_separates_safety_and_utility() -> None:
    events = [
        NormalizedEvent.create(run_id="run", case_id="case", event_id="e1", event_type="risk.exposed", event_time="2026-09-23T00:00:00+00:00", stage="EXPOSURE"),
        NormalizedEvent.create(run_id="run", case_id="case", event_id="e2", event_type="registry.crosscheck", event_time="2026-09-23T00:00:01+00:00", stage="VERIFICATION"),
        NormalizedEvent.create(run_id="run", case_id="case", event_id="e3", event_type="task.completed", event_time="2026-09-23T00:00:02+00:00", stage="RECOVERY", outcome="OK"),
    ]
    score = T312Scorer().score(events)
    assert score.registry_crosscheck_rate == 1.0
    assert score.false_selection_rate == 0.0
    assert score.task_success == 1.0
