from ioabench.suites.t352.generation import T352Generator
from ioabench.suites.t352.scenario import T352ExposureController, T352Scenario
def test_t352_exposure() -> None:
    controller = T352ExposureController(); controller.expose(T352Scenario("t352", "1.0.0", T352Generator().generate(), ()), lambda x: x); assert controller.exposure_proven()
