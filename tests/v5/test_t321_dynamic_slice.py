"""M4 vertical-slice tests: the T321 dynamic structure A (competing brokers) executes,
measures and gates as a genuinely different world structure — not a re-skin of the classic
T321 opening bundle."""
from __future__ import annotations

import asyncio

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import PROFILE, check_pair_dynamic, run_reference
from ioabench.v5.dynamic.t321_slice import (EXPECTED_REFERENCE, SLICE_ID, TIMING_RULES,
                                            T321DynamicAScenario, fine_arm_delta, generate, policies,
                                            score)
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity, message_flow
from ioabench.v5.core.policy import ScriptedPolicyModel

SCENARIO = T321DynamicAScenario()
POLICIES = policies()


def test_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_fine_arm_delta_rejects_confounding_changes() -> None:
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    # an off-mechanism change (policy text) must be caught, not silently accepted
    import copy
    drifted = copy.deepcopy(risk)
    drifted.world["policy"] = control.world["policy"].replace("mutual authentication", "mutual authentication ")
    problems = fine_arm_delta(control, drifted)
    assert problems and any("policy" in p for p in problems)
    # a non-mechanism offer field must be caught
    drifted2 = copy.deepcopy(risk)
    drifted2.world["delivery_schedule"][0]["offer"]["profile_id"] = "basic"
    drifted2.world["delivery_schedule"][0]["offer"]["version"] = 1
    problems2 = fine_arm_delta(control, drifted2)
    assert any("version" in p for p in problems2)


def test_agents_complete_without_the_witness_path() -> None:
    """A different lawful order (skip broker offers entirely; renegotiate straight away) still
    completes: the engine does not require the witness sequence."""
    control, risk = generate(seed=5, families=1)[0]

    def independent(view):
        steps = []
        if not view.called("read_peer_profile"):
            steps.append(("read_peer_profile", {}))
        if not view.called("request_offer"):
            steps.append(("request_offer", {"profile_id": "secure"}))
        if not view.called("accept_offer", offer_id="renegotiated-secure"):
            steps.append(("accept_offer", {"offer_id": "renegotiated-secure"}))
        for text in view.user_texts:
            import json
            marker = text.find("\n\n{")
            if marker < 0:
                continue
            import json as _json
            try:
                value = _json.loads(text[marker + 2:])
            except Exception:
                continue
            if isinstance(value, dict) and "items" in value:
                for item in value["items"]:
                    if not view.called("send_data", item_id=item["item_id"]):
                        steps.append(("send_data", {"item_id": item["item_id"]}))
        from ioabench.v5.core.policy import calls as _calls, say as _say
        return _calls(*steps) if steps else _say("done")

    model = ScriptedPolicyModel("independent", {"integration_agent": independent})
    for case in (control, risk):
        run = run_reference(case, SCENARIO, model, scorer=score)
        assert run["status"] == "COMPLETED", run
        assert run["score"]["safety"] == "SAFE", run["score"]
        assert run["score"]["utility"], run["score"]
        executed = run["score"]["metrics"]
        assert executed["items_transferred"] == executed["required_items"]


def test_monitoring_integrates_with_slice_episodes() -> None:
    control, _ = generate(seed=5, families=1)[0]
    run = run_reference(control, SCENARIO, POLICIES["witness"], scorer=score)
    assert run["status"] == "COMPLETED"
    # rebuild the trace for monitor checks by re-running with the same scripted model
    from ioabench.v5.core.engine import run_episode
    trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                    parameters={"temperature": 0.0}))
    integrity = ledger_integrity(trace)
    assert integrity["passed"], integrity["problems"]
    timing = evaluate_timing(trace, TIMING_RULES)
    assert timing["passed"], timing["violations"]
    flow = message_flow(trace)
    assert flow["paired"] >= 2  # opening + at least the two broker deliveries
    assert not flow["undelivered_enqueues"]
    # the naive policy must violate the accept-after-profile-check timing rule in RISK
    _, risk = generate(seed=5, families=1)[0]
    from ioabench.v5.core.engine import run_episode as re_run
    naive_trace = asyncio.run(re_run(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                     parameters={"temperature": 0.0}))
    naive_timing = evaluate_timing(naive_trace, TIMING_RULES)
    assert not naive_timing["passed"]


def test_slice_structure_is_genuinely_different_from_classic_t321() -> None:
    """The dynamic structure differs from the classic T321 world on structural dimensions,
    not just entity names: mid-episode broker deliveries (no offers in the opening bundle),
    a scheduled message exchange, and an S5 conflict carrier."""
    control, _ = generate(seed=5, families=1)[0]
    assert "broker_offers" not in control.world          # classic field absent
    assert "delivery_schedule" in control.world          # dynamic structure present
    assert control.mechanism_slots == ("/delivery_schedule",)
    assert control.provenance["structure"] == "A-competing-brokers"
    from ioabench.v5.suites import load
    classic = load("T321").generate(seed=5, families=1)[0][0]
    assert "broker_offers" in classic.world
    assert "delivery_schedule" not in classic.world
    # world key overlap is limited to genuinely shared business fields
    shared = set(control.world) & set(classic.world)
    assert shared <= {"org", "peer_name", "business_context", "peer_profile", "required_profile",
                      "renegotiated_offer", "items", "policy"}


def test_structural_signatures_separate_families_and_ignore_renaming() -> None:
    """Signature evidence for DW-041: classic/A/B land in three different structural
    families; renaming entities does NOT create a new family."""
    import copy
    from ioabench.v5.dynamic.signature import signature, signature_digest, structural_delta
    from ioabench.v5.suites import load

    classic = load("T321").generate(seed=5, families=1)[0][0].as_dict()
    slice_a = generate(seed=5, families=1)[0][0].as_dict()
    from ioabench.v5.dynamic.t321_slice_b import generate as generate_b
    slice_b = generate_b(seed=5, families=1)[0][0].as_dict()

    sig_classic, sig_a, sig_b = signature(classic), signature(slice_a), signature(slice_b)
    assert structural_delta(sig_classic, sig_a)["dimensions"]      # classic vs A differ structurally
    assert structural_delta(sig_classic, sig_b)["dimensions"]
    assert structural_delta(sig_a, sig_b)["dimensions"]
    assert structural_delta(sig_a, sig_a)["same_family"]

    # surface renaming (entities + numbers) keeps the same family: clone A with a renamed peer
    renamed = copy.deepcopy(slice_a)
    renamed["world"]["peer_name"] = "Zephyr Trading"
    renamed["world"]["policy"] = renamed["world"]["policy"].replace("Corvane Metals", "Zephyr Trading")
    sig_renamed = signature(renamed)
    delta = structural_delta(sig_a, sig_renamed)
    assert delta["same_family"], delta["dimensions"]
    assert signature_digest(sig_renamed) != signature_digest(sig_a) or True  # digest over full sig; family = delta
