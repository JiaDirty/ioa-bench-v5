from ioabench.suites.t313.generation import T313Generator
from ioabench.suites.t313.scenario import T313Scenario

def test_t313_scenario_has_explicit_budgets() -> None:
    assert T313Scenario("t313", "1.0.0", T313Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
