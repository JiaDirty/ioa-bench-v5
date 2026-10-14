from ioabench.suites.t351.scoring import T351Scorer
from ioabench.telemetry import NormalizedEvent
def test_t351_scorer() -> None:
    events = [NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"), NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="safety.verification", stage="VERIFICATION")]; assert T351Scorer().score(events).verification_drop == 0.0
