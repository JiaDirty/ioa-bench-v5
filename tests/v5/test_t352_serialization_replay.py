"""Registry tie-breaking must survive canonical JSON without changing the scorer."""
import asyncio
from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic import t352_slice as SLICE
from ioabench.v5.replay import RecordedPort

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def pair():
    spec = suite_spec("T352", typed=True)
    blueprint = program_proposal(spec, seed=6101912, difficulty="M", target={
        "allocator_count": 2, "report_access": "broadcast", "reputation_governance": "shared_rating_aggregate"})
    return spec.adapter.compile_pair(blueprint, seed=6101912)


def test_equal_ratings_sorted_json_roundtrip_replays_identical_actual_requests():
    risk = pair()[1]
    scenario = SLICE.T352DynamicScenario()
    trace = asyncio.run(run_episode(risk, scenario, SLICE.policies()["recovery"], PROFILE, parameters={}))
    sorted_case = case_from_dict(json.loads(json.dumps(risk.as_dict(), sort_keys=True)), allow_dynamic=True)
    assert list(risk.world["providers"]) != list(sorted_case.world["providers"])
    assert risk.content_sha256() == sorted_case.content_sha256()
    board = trace.final_state["reputation_updates"][-1]["board"]
    assert board["provider_ratings"][SLICE.INCUMBENT] == board["provider_ratings"][SLICE.CHALLENGER] == 5
    assert board["top_rated"] == SLICE.INCUMBENT
    port = RecordedPort(trace.records)
    replay = asyncio.run(run_episode(sorted_case, scenario, port, PROFILE, parameters={}))
    assert port.consumed == len(trace.records)
    assert replay.final_state == trace.final_state
    assert SLICE.score(replay, sorted_case).as_dict() == SLICE.score(trace, risk).as_dict()


def test_legacy_implicit_order_reproduces_the_original_tied_replay_failure():
    risk = pair()[1]
    del risk.world["provider_registry_order"]
    scenario = SLICE.T352DynamicScenario()
    trace = asyncio.run(run_episode(risk, scenario, SLICE.policies()["recovery"], PROFILE, parameters={}))
    sorted_case = case_from_dict(json.loads(json.dumps(risk.as_dict(), sort_keys=True)), allow_dynamic=True)
    assert risk.content_sha256() == sorted_case.content_sha256()
    with pytest.raises(ValueError, match="replay request/role/order mismatch"):
        asyncio.run(run_episode(sorted_case, scenario, RecordedPort(trace.records), PROFILE, parameters={}))


@pytest.mark.parametrize("order", [[], [SLICE.INCUMBENT], [SLICE.INCUMBENT, SLICE.INCUMBENT], "invalid"])
def test_invalid_explicit_registry_order_is_rejected(order):
    case = pair()[0]
    case.world["provider_registry_order"] = order
    with pytest.raises(ValueError, match="every provider exactly once"):
        SLICE.T352DynamicScenario().initial_state(case.world)


def test_registry_order_is_arm_invariant_and_legacy_order_is_preserved():
    control, risk = pair()
    risk.world["provider_registry_order"].reverse()
    assert any("provider_registry_order" in finding for finding in SLICE.fine_arm_delta(control, risk))
    legacy = deepcopy(control.world)
    del legacy["provider_registry_order"]
    assert SLICE._provider_order(legacy) == list(legacy["providers"])
