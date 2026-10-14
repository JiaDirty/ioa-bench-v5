from ioabench.suites.t352.generation import T352Generator
from ioabench.suites.t352.scenario import T352Scenario
def test_t352_scenario() -> None:
    assert T352Scenario("t352", "1.0.0", T352Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
