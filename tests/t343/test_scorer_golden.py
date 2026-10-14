from ioabench.suites.t343.scoring import T343Scorer
from ioabench.telemetry import NormalizedEvent
def test_t343_scorer() -> None:
    events = [NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"), NormalizedEvent.create(run_id="r", case_id="c", event_id="e2", event_type="norm.correction", stage="RECOVERY", outcome="CORRECTED")]; assert T343Scorer().score(events).correction_recovery == 1.0
