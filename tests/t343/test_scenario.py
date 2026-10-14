from ioabench.suites.t343.generation import T343Generator
from ioabench.suites.t343.scenario import T343Scenario
def test_t343_scenario() -> None:
    assert T343Scenario("t343", "1.0.0", T343Generator().generate(), ()).document()["budgets"]["max_model_calls"] == 4
