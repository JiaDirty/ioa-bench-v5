from ioabench.suites.t323.generation import T323Generator
from ioabench.suites.t323.scenario import T323Scenario

def test_t323_scenario_has_explicit_budgets() -> None:
    assert T323Scenario("t323", "1.0.0", T323Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
