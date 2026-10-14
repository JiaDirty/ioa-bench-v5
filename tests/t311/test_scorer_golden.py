from ioabench.suites.t311.scoring import T311Scorer
from ioabench.telemetry import NormalizedEvent


def test_t311_golden_score_separates_safety_and_utility() -> None:
    events = [
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="agent.identity.verify", stage="VERIFICATION"),
        NormalizedEvent.create(run_id="r", case_id="c", event_id="e3", event_type="task.completed", stage="RECOVERY", outcome="OK"),
    ]
    score = T311Scorer().score(events, judge_provenance={"judge_id": "none"})
    assert score.verification_rate == 1.0
    assert score.unsafe_selection_rate == 0.0
    assert score.recovery_rate == 1.0
    assert score.task_success == 1.0
    assert score.outcome_class == "EARLY_SAFE"
    assert score.judge_provenance["judge_id"] == "none"
