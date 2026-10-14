from ioabench.suites.t351.generation import T351Generator
from ioabench.suites.t351.scenario import T351Scenario
def test_t351_scenario() -> None:
    assert T351Scenario("t351", "1.0.0", T351Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
