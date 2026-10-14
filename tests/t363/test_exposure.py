from ioabench.suites.t363.generation import T363Generator
from ioabench.suites.t363.scenario import T363ExposureController, T363Scenario
def test_t363_exposure_labels_event() -> None:
    controller = T363ExposureController(); controller.expose(T363Scenario("t363", "1.0.0", T363Generator().generate(), ()), lambda x: x); assert any(e.get("validity") == "SIMULATION_ONLY" for e in controller.proof_events)
