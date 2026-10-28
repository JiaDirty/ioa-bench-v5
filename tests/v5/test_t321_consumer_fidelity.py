from dataclasses import replace

from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.dynamic import t321_slice
from ioabench.v5.dynamic.gates import check_pair_dynamic


def gate(scenario):
    spec = suite_spec("T321", typed=True)
    bp = program_proposal(spec, seed=619017, difficulty="M", target={"peer_profile_delivery": "broker_gamma"})
    pair = spec.adapter.compile_pair(bp, seed=619017)
    return check_pair_dynamic(*pair, scenario=scenario, scorer=spec.scorer, policies=spec.policies,
        expected=spec.expected, fine_arm_delta=spec.adapter.verify_arm_delta)


def test_actual_scheduled_delivery_and_profile_results_have_fidelity_evidence():
    result = gate(t321_slice.T321DynamicAScenario())
    assert result["passed"], result["failures"]
    assert all(row["execution_fidelity"]["passed"] for row in result["runs"])
    assert any(row["execution_fidelity"]["checks"] for row in result["runs"])


def test_premature_profile_access_is_rejected_even_when_transfer_utility_succeeds():
    class EarlyProfile(t321_slice.T321DynamicAScenario):
        def tools(self, world):
            tools = super().tools(world)
            tools["read_peer_profile"] = replace(tools["read_peer_profile"], handler=lambda ctx, args: dict(world["peer_profile"]))
            return tools

    result = gate(EarlyProfile())
    assert not result["passed"] and any("publication timing" in failure for failure in result["failures"])
    assert all(row["score"]["utility"] for row in result["runs"] if "witness" in row["policy"])


def test_wrong_scheduled_message_source_is_rejected_even_with_useful_secure_renegotiation():
    class WrongMessage(t321_slice.T321DynamicAScenario):
        async def after_turn(self, env, agent_id):
            await super().after_turn(env, agent_id)
            inbox = env.inboxes[agent_id]
            if inbox:
                inbox[-1] = inbox[-1].replace("Message from", "Incorrect source from")

    result = gate(WrongMessage())
    assert not result["passed"] and any("exact scheduled message" in failure for failure in result["failures"])
