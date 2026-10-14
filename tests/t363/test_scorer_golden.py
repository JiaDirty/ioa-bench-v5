from ioabench.suites.t363.scoring import T363Scorer
from ioabench.telemetry import NormalizedEvent
def test_t363_scorer_labels_result() -> None:
    score = T363Scorer().score([NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")]); assert score.validity == "SIMULATION_ONLY"
