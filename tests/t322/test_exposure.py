from ioabench.suites.t322.generation import T322Generator
from ioabench.suites.t322.scenario import T322ExposureController, T322Scenario

def test_t322_exposure_reaches_model() -> None:
    controller = T322ExposureController()
    controller.expose(T322Scenario("t322", "1.0.0", T322Generator().generate(), ()), lambda value: value)
    assert controller.exposure_proven()
