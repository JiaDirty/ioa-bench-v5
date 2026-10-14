import asyncio
from pathlib import Path
from ioabench.models import ModelProfile
from ioabench.runtime.disclosure_inference import DisclosureBaseline, build_disclosure_fixture, execute_disclosure
ROOT = Path(__file__).parents[2]
def run(suite, policy): return asyncio.run(execute_disclosure(ROOT, build_disclosure_fixture(suite), DisclosureBaseline(policy), ModelProfile("mock", "offline-disclosure", {}, {}), run_id=f"{suite}-{policy}"))
def test_disclosure_baselines_are_causal():
    assert run("T332", "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run("T332", "naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run("T332", "recovery")["score"]["outcome_class"] == "LATE_RECOVERY"
def test_inference_baselines_are_causal():
    assert run("T333", "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run("T333", "naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run("T333", "recovery")["score"]["outcome_class"] == "LATE_RECOVERY"
def test_two_tested_agents_and_a2a_replay():
    result = run("T332", "safe")
    assert len(result["replay"]["agents"]) == 2
    assert any(event["event_type"] == "agent.message.sent" for event in result["replay"]["timeline"])
