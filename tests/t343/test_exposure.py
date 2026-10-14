from ioabench.suites.t343.generation import T343Generator
from ioabench.suites.t343.scenario import T343ExposureController, T343Scenario
def test_t343_exposure() -> None:
    controller = T343ExposureController(); controller.expose(T343Scenario("t343", "1.0.0", T343Generator().generate(), ()), lambda x: x); assert controller.exposure_proven()
