from ioabench.suites.t342.generation import T342Generator
from ioabench.suites.t342.scenario import T342Scenario
def test_t342_scenario() -> None:
    assert T342Scenario("t342", "1.0.0", T342Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
