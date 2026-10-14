from pathlib import Path
from ioabench.runtime.deliberation_norm import run_deliberation_baseline
ROOT=Path(__file__).parents[2]
def test_t341_baselines():
    assert run_deliberation_baseline(ROOT,"T341","safe")["score"]["outcome_class"]=="EARLY_SAFE"; assert run_deliberation_baseline(ROOT,"T341","naive")["score"]["outcome_class"]=="FULL_FAILURE"; assert run_deliberation_baseline(ROOT,"T341","recovery")["score"]["outcome_class"]=="LATE_RECOVERY"
def test_t343_baselines():
    assert run_deliberation_baseline(ROOT,"T343","safe")["score"]["outcome_class"]=="EARLY_SAFE"; assert run_deliberation_baseline(ROOT,"T343","naive")["score"]["outcome_class"]=="FULL_FAILURE"; assert run_deliberation_baseline(ROOT,"T343","recovery")["score"]["outcome_class"]=="LATE_RECOVERY"

def test_deliberation_replay_preserves_tools_and_discussion_events():
    result = run_deliberation_baseline(ROOT, "T341", "safe")
    replay = result["replay"]
    assert any(event["event_type"] == "deliberation.action" for event in replay["timeline"])
    assert any(event["event_type"] == "agent.message.sent" and event["protocol"] == "A2A" for event in replay["timeline"])
    assert all(event.get("target_agent_id") == "decider" for event in replay["timeline"] if event["event_type"] == "agent.message.sent")
    assert all(record["request"]["tools"] for record in replay["model_records"])

def test_norm_replay_preserves_episode_transitions():
    result = run_deliberation_baseline(ROOT, "T343", "safe")
    replay = result["replay"]
    assert sum(event["event_type"] == "deliberation.episode" for event in replay["timeline"]) == 3
    assert len({record["agent_id"] for record in replay["model_records"]}) == 2
    assert all(event["event_type"] != "agent.message.sent" or event.get("target_agent_id") != "discussion-room" for event in replay["timeline"])
