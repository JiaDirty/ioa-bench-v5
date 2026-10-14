from ioabench.suites.t362.generation import T362Generator
from ioabench.suites.t362.scenario import T362Scenario
def test_t362_scenario_labels_claim_boundary() -> None:
    document = T362Scenario("t362", "1.0.0", T362Generator().generate(), ()).document(); assert document["simulation_only"] and document["validity"] == "SIMULATION_ONLY"
