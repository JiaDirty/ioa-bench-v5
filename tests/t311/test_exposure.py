from ioabench.suites.t311.generation import T311Generator
from ioabench.suites.t311.scenario import T311ExposureController, T311Scenario


def test_t311_risk_exposure_reaches_tested_model_and_is_proven() -> None:
    scenario = T311Scenario("t311-exposure", "1.0.0", T311Generator().generate(), ())
    seen = []
    controller = T311ExposureController()
    controller.expose(scenario, seen.append)
    assert "condition" not in seen[0]
    assert "case_id" not in seen[0]
    assert "agent_claim" in seen[0]
    assert controller.exposure_proven()
