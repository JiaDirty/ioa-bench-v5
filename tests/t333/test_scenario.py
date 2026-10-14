from ioabench.suites.t333.generation import T333Generator
from ioabench.suites.t333.scenario import T333Scenario


def test_t333_scenario_has_explicit_budgets() -> None:
    assert T333Scenario("t333", "1.0.0", T333Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
