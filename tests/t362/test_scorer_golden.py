from ioabench.suites.t362.scoring import T362Scorer
from ioabench.telemetry import NormalizedEvent
def test_t362_scorer_labels_result() -> None:
    score = T362Scorer().score([NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")]); assert score.validity == "SIMULATION_ONLY"
