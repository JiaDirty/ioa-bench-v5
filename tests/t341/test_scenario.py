from ioabench.suites.t341.generation import T341Generator
from ioabench.suites.t341.scenario import T341Scenario
def test_t341_scenario() -> None:
    assert T341Scenario("t341", "1.0.0", T341Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
