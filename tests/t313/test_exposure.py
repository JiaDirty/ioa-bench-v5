from ioabench.suites.t313.generation import T313Generator
from ioabench.suites.t313.scenario import T313ExposureController, T313Scenario

def test_t313_exposure_reaches_model() -> None:
    controller = T313ExposureController()
    controller.expose(T313Scenario("t313", "1.0.0", T313Generator().generate(), ()), lambda value: value)
    assert controller.exposure_proven()
