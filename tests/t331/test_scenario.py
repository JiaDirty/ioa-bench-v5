from ioabench.suites.t331.generation import T331Generator
from ioabench.suites.t331.scenario import T331Scenario


def test_t331_scenario_has_explicit_limits() -> None:
    document = T331Scenario("t331", "1.0.0", T331Generator().generate(), ()).document()
    assert document["budgets"]["max_model_calls"] == 4
    assert document["exposure"]["must_reach_tested_model"] is True
