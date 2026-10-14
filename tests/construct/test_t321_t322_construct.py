import asyncio
from dataclasses import asdict
from pathlib import Path
from ioabench.models import ModelProfile
from ioabench.runtime.protocol_state_machine import ProtocolBaseline, build_protocol_case_from_skeleton, build_protocol_fixture, execute_protocol
from ioabench.suites.t321.generation import T321Generator
from ioabench.suites.t322.generation import T322Generator

ROOT = Path(__file__).parents[2]

def run(suite, policy):
    return asyncio.run(execute_protocol(ROOT, build_protocol_fixture(suite), ProtocolBaseline(policy), ModelProfile("mock", "offline-protocol", {}, {}), run_id=f"{suite}-{policy}"))

def test_protocol_baselines_are_action_sensitive():
    assert run("T321", "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run("T321", "naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run("T321", "recovery")["score"]["outcome_class"] == "LATE_RECOVERY"

def test_interoperability_baselines_distinguish_duplicate_and_compensation():
    assert run("T322", "safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run("T322", "naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run("T322", "recovery")["score"]["outcome_class"] == "LATE_RECOVERY"

def test_replay_has_separate_tested_agents_and_real_protocol_state():
    result = run("T321", "safe")
    assert len(result["replay"]["agents"]) == 2
    assert result["replay"]["world_snapshot"]["session_state"] == "SECURE"
    assert any(event["event_type"] == "agent.message.sent" for event in result["replay"]["timeline"])

def test_oracle_and_visible_protocol_are_separate():
    case = build_protocol_fixture("T321")
    changed = build_protocol_fixture("T321")
    changed["oracle_payload"]["safe_version"] = "legacy-v1"
    left = asyncio.run(execute_protocol(ROOT, case, ProtocolBaseline("safe"), ModelProfile("mock", "offline", {}, {})))
    right = asyncio.run(execute_protocol(ROOT, changed, ProtocolBaseline("safe"), ModelProfile("mock", "offline", {}, {})))
    assert [record["request"] for record in left["replay"]["model_records"]] == [record["request"] for record in right["replay"]["model_records"]]


def test_generated_protocol_skeletons_drive_protocol_state():
    for suite, generator in (("T321", T321Generator), ("T322", T322Generator)):
        case = build_protocol_case_from_skeleton(asdict(generator().generate(seed=2, mechanism_index=0, condition="RISK")))
        result = asyncio.run(execute_protocol(ROOT, case, ProtocolBaseline("safe"), ModelProfile("mock", "offline", {}, {})))
        assert result["score"]["task_utility"] is True
        assert result["replay"]["scenario"]["source_records"]["protocol"] == case["visible"]
