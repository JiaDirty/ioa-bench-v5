from ioabench.suites.t341.generation import T341Generator
from ioabench.suites.t341.scenario import T341ExposureController, T341Scenario
def test_t341_exposure() -> None:
    controller = T341ExposureController(); controller.expose(T341Scenario("t341", "1.0.0", T341Generator().generate(), ()), lambda x: x); assert controller.exposure_proven()
