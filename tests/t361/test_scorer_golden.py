from ioabench.suites.t361.scoring import T361Scorer
from ioabench.telemetry import NormalizedEvent
def test_t361_scorer_labels_result() -> None:
    score = T361Scorer().score([NormalizedEvent.create(run_id="r", case_id="c", event_id="e", event_type="risk.exposed", stage="EXPOSURE")]); assert score.validity == "SIMULATION_ONLY"
