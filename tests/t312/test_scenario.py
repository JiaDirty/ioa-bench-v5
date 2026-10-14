from ioabench.suites.t312.generation import T312Generator
from ioabench.suites.t312.scenario import T312ExposureController, T312Scenario


def test_t312_scenario_documents_budgets_and_exposure() -> None:
    scenario = T312Scenario("t312", "1.0.0", T312Generator().generate(), ())
    seen = []
    T312ExposureController().expose(scenario, seen.append)
    assert seen and scenario.document()["budgets"]["max_model_calls"] == 4


def test_t312_exposure_proof_reaches_model() -> None:
    controller = T312ExposureController()
    scenario = T312Scenario("t312", "1.0.0", T312Generator().generate(), ())
    controller.expose(scenario, lambda payload: payload)
    assert controller.exposure_proven()
