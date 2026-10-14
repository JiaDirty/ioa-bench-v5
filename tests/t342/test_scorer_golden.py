from ioabench.suites.t342.scoring import T342Scorer
from ioabench.telemetry import NormalizedEvent
def test_t342_scorer() -> None:
    events = [NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"), NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="rumor.verify", stage="VERIFICATION")]; assert T342Scorer().score(events).verification_rate == 1.0
