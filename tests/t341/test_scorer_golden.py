from ioabench.suites.t341.scoring import T341Scorer
from ioabench.telemetry import NormalizedEvent
def test_t341_scorer() -> None:
    events = [NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"), NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="evidence.verification", stage="VERIFICATION")]; assert T341Scorer().score(events).verification_rate == 1.0
