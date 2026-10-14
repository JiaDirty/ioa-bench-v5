from ioabench.suites.t321.generation import T321Generator
from ioabench.suites.t321.scenario import T321ExposureController, T321Scenario

def test_t321_exposure_reaches_model() -> None:
    controller = T321ExposureController()
    controller.expose(T321Scenario("t321", "1.0.0", T321Generator().generate(), ()), lambda value: value)
    assert controller.exposure_proven()
