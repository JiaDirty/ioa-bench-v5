from ioabench.suites.t323.generation import T323Generator
from ioabench.suites.t323.scenario import T323ExposureController, T323Scenario

def test_t323_exposure_reaches_model() -> None:
    controller = T323ExposureController()
    controller.expose(T323Scenario("t323", "1.0.0", T323Generator().generate(), ()), lambda value: value)
    assert controller.exposure_proven()
