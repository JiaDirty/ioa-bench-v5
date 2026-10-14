from ioabench.suites.t353.scoring import T353Scorer
from ioabench.telemetry import NormalizedEvent
def test_t353_scorer() -> None:
    event = NormalizedEvent.create(run_id="r", case_id="c", event_id="e1", event_type="risk.exposed", stage="EXPOSURE"); assert T353Scorer().score([event]).independent_comparison_rate == 0.0
