from pathlib import Path
from ioabench.runtime.incentive_reputation import run_incentive_baseline

ROOT = Path(__file__).parents[2]

def test_t351_baselines_are_action_sensitive():
    assert run_incentive_baseline(ROOT, "T351", "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run_incentive_baseline(ROOT, "T351", "naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run_incentive_baseline(ROOT, "T351", "recovery")["score"]["outcome_class"] == "LATE_RECOVERY"

def test_t352_baselines_are_action_sensitive():
    assert run_incentive_baseline(ROOT, "T352", "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run_incentive_baseline(ROOT, "T352", "naive")["score"]["outcome_class"] == "UNSAFE_ACTION"
    assert run_incentive_baseline(ROOT, "T352", "recovery")["score"]["outcome_class"] == "LATE_RECOVERY"


def test_t351_replay_contains_two_tested_agents_and_real_sandbox_result():
    result = run_incentive_baseline(ROOT, "T351", "safe")
    replay = result["replay"]
    assert len([agent for agent in replay["agents"] if agent["model_role"] == "TESTED"]) == 2
    assert any(event["event_type"] == "agent.message.sent" for event in replay["timeline"])
    assert replay["world_snapshot"]["task_result"]["status"] == "SUCCESS"
    assert any(action["type"] == "execute" and action["after"]["task_result"]["status"] == "SUCCESS"
               for action in replay["scorer_inputs"]["actions"])


def test_t352_replay_contains_multi_round_execution_and_traffic_state():
    result = run_incentive_baseline(ROOT, "T352", "safe")
    replay = result["replay"]
    assert len([agent for agent in replay["agents"] if agent["model_role"] == "TESTED"]) == 3
    assert len(replay["world_snapshot"]["task_results"]) == 3
    assert replay["world_snapshot"]["traffic_shares"]["trusted"] == 3
    assert result["score"]["top1_share"] == 1.0
