from ioabench.suites.t361.generation import T361Generator
from ioabench.suites.t361.scenario import T361ExposureController, T361Scenario
def test_t361_exposure_labels_event() -> None:
    controller = T361ExposureController(); controller.expose(T361Scenario("t361", "1.0.0", T361Generator().generate(), ()), lambda x: x); assert any(e.get("validity") == "SIMULATION_ONLY" for e in controller.proof_events)
