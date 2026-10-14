from ioabench.suites.t353.generation import T353Generator
from ioabench.suites.t353.scenario import T353ExposureController, T353Scenario
def test_t353_exposure() -> None:
    controller = T353ExposureController(); controller.expose(T353Scenario("t353", "1.0.0", T353Generator().generate(), ()), lambda x: x); assert controller.exposure_proven()
