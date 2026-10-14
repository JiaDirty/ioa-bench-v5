from ioabench.suites.t363.generation import T363Generator
from ioabench.suites.t363.scenario import T363Scenario
def test_t363_scenario_labels_claim_boundary() -> None:
    document = T363Scenario("t363", "1.0.0", T363Generator().generate(), ()).document(); assert document["simulation_only"] and document["validity"] == "SIMULATION_ONLY"
