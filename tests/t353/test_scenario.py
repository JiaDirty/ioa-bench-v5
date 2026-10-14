from ioabench.suites.t353.generation import T353Generator
from ioabench.suites.t353.scenario import T353Scenario
def test_t353_scenario() -> None:
    assert T353Scenario("t353", "1.0.0", T353Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
