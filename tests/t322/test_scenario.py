from ioabench.suites.t322.generation import T322Generator
from ioabench.suites.t322.scenario import T322Scenario

def test_t322_scenario_has_explicit_budgets() -> None:
    assert T322Scenario("t322", "1.0.0", T322Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
