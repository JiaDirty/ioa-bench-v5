from ioabench.suites.t331.generation import T331Generator
from ioabench.suites.t331.scenario import T331ExposureController, T331Scenario


def test_t331_exposure_reaches_model() -> None:
    controller = T331ExposureController()
    controller.expose(T331Scenario("t331", "1.0.0", T331Generator().generate(), ()), lambda payload: payload)
    assert controller.exposure_proven()
