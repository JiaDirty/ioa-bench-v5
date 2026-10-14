from ioabench.suites.t362.generation import T362Generator
from ioabench.suites.t362.scenario import T362ExposureController, T362Scenario
def test_t362_exposure_labels_event() -> None:
    controller = T362ExposureController(); controller.expose(T362Scenario("t362", "1.0.0", T362Generator().generate(), ()), lambda x: x); assert any(e.get("validity") == "SIMULATION_ONLY" for e in controller.proof_events)
