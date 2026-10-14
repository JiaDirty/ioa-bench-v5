from ioabench.suites.t332.generation import T332Generator
from ioabench.suites.t332.scenario import T332ExposureController, T332Scenario


def test_t332_exposure_reaches_model() -> None:
    controller = T332ExposureController()
    controller.expose(T332Scenario("t332", "1.0.0", T332Generator().generate(), ()), lambda payload: payload)
    assert controller.exposure_proven()
