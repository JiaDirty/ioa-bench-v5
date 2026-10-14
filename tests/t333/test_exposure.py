from ioabench.suites.t333.generation import T333Generator
from ioabench.suites.t333.scenario import T333ExposureController, T333Scenario


def test_t333_exposure_reaches_model() -> None:
    controller = T333ExposureController()
    controller.expose(T333Scenario("t333", "1.0.0", T333Generator().generate(), ()), lambda payload: payload)
    assert controller.exposure_proven()
