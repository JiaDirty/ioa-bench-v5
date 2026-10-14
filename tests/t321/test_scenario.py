from ioabench.suites.t321.generation import T321Generator
from ioabench.suites.t321.scenario import T321Scenario

def test_t321_scenario_has_explicit_budgets() -> None:
    assert T321Scenario("t321", "1.0.0", T321Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
