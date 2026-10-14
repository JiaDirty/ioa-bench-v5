from ioabench.suites.t361.generation import T361Generator
from ioabench.suites.t361.scenario import T361Scenario
def test_t361_scenario_labels_claim_boundary() -> None:
    document = T361Scenario("t361", "1.0.0", T361Generator().generate(), ()).document(); assert document["simulation_only"] and document["validity"] == "SIMULATION_ONLY"
