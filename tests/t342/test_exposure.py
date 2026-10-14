from ioabench.suites.t342.generation import T342Generator
from ioabench.suites.t342.scenario import T342ExposureController, T342Scenario
def test_t342_exposure() -> None:
    controller = T342ExposureController(); controller.expose(T342Scenario("t342", "1.0.0", T342Generator().generate(), ()), lambda x: x); assert controller.exposure_proven()
