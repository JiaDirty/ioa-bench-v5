from ioabench.suites.t312.generation import T312Generator
from ioabench.suites.t312.scenario import T312ExposureController, T312Scenario


def test_t312_risk_exposure_reaches_model_input() -> None:
    controller = T312ExposureController()
    scenario = T312Scenario("t312-exposure", "1.0.0", T312Generator().generate(condition="RISK"), ())
    received = []
    controller.expose(scenario, received.append)
    assert received
    assert "condition" not in received[0]
    assert "case_id" not in received[0]
    assert controller.exposure_proven()
