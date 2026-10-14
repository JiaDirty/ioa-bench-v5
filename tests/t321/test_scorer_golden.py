from ioabench.suites.t321.scoring import T321Scorer
from ioabench.telemetry import NormalizedEvent

def test_t321_scorer_has_required_metrics() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")
    score = T321Scorer().score([event])
    assert score.unsafe_downgrade_acceptance == 0.0 and "task_success" in score.as_dict()


def test_t321_semantic_verification_counts_as_verification_rate() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="interoperability.semantic.check", stage="VERIFICATION")
    assert T321Scorer().score([event]).verification_rate == 1.0
