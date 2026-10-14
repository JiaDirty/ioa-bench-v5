from ioabench.suites.t332.generation import T332Generator
from ioabench.suites.t332.scenario import T332Scenario


def test_t332_scenario_has_explicit_budgets() -> None:
    assert T332Scenario("t332", "1.0.0", T332Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
