from ioabench.suites.t311.generation import T311Generator
from ioabench.suites.t311.scenario import T311Scenario


def test_t311_scenario_has_explicit_budget_and_replay_contract() -> None:
    skeleton = T311Generator().generate()
    scenario = T311Scenario("t311-case", "1.0.0", skeleton, ({"agent_id": "agent-1", "org_id": "org-a", "role_id": "reviewer", "actor_type": "TESTED_MODEL"},))
    document = scenario.document()
    assert document["exposure"]["must_reach_tested_model"] is True
    assert document["replay"]["required"] is True
    assert document["budgets"]["max_model_calls"] > 0
