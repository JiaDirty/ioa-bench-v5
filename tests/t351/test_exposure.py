from ioabench.suites.t351.generation import T351Generator
from ioabench.suites.t351.scenario import T351ExposureController, T351Scenario
def test_t351_exposure() -> None:
    controller = T351ExposureController(); controller.expose(T351Scenario("t351", "1.0.0", T351Generator().generate(), ()), lambda x: x); assert controller.exposure_proven()
