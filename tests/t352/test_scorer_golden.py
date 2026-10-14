from ioabench.suites.t352.scoring import T352Scorer
from ioabench.telemetry import NormalizedEvent
def test_t352_scorer() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"); assert T352Scorer().score([event]).alternative_comparison_rate == 0.0
