"""M7 SIMULATION_ONLY cluster tests: the T361/T362/T363 dynamic slices are thin delivery-
structure variants that inherit the classic scenarios and delegate score/policies/persona
verbatim — the tests prove the delegation is semantically transparent and the new delivery
structures are executable, gated, and signature-distinct."""
from __future__ import annotations

import asyncio

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.suites import load

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def _slice_case(sid: str, module):
    control, risk = module.generate(seed=5, families=1)[0]
    report = check_pair_dynamic(control, risk, scenario=module.T361DynamicScenario() if sid == "T361" else
                                module.T362DynamicScenario() if sid == "T362" else
                                module.T363DynamicScenario(),
                                scorer=module.score, policies=module.policies(),
                                expected=module.EXPECTED_REFERENCE,
                                fine_arm_delta=module.fine_arm_delta)
    assert report["passed"], (report["pair_id"], report["failures"])
    return control, risk


@pytest.mark.parametrize("sid", ["T361", "T362", "T363"])
def test_simulation_slice_pairs_pass_dynamic_gates(sid: str) -> None:
    module = __import__(f"ioabench.v5.dynamic.{sid.lower()}_slice", fromlist=["generate"])
    _slice_case(sid, module)


@pytest.mark.parametrize("sid", ["T361", "T362", "T363"])
def test_simulation_slice_scoring_is_delegated_verbatim(sid: str) -> None:
    """The slice scorer must return the same safety/utility/abstain as the classic scorer on
    the same trace — zero semantics drift through the slice layer."""
    module = __import__(f"ioabench.v5.dynamic.{sid.lower()}_slice", fromlist=["score"])
    classic = load(sid)
    control, risk = module.generate(seed=5, families=1)[0]
    scenario = (module.T361DynamicScenario() if sid == "T361" else
                module.T362DynamicScenario() if sid == "T362" else
                module.T363DynamicScenario())
    for case in (control, risk):
        run = run_reference(case, scenario, module.policies()["witness"], scorer=module.score)
        assert run["status"] == "COMPLETED", run
        trace = run_episode_delegated(case, scenario)
        slice_score = module.score(trace, case)
        classic_score = classic.score(trace, case)
        assert slice_score.safety == classic_score.safety
        assert slice_score.utility == classic_score.utility
        assert slice_score.abstain == classic_score.abstain
        assert len(slice_score.violations) == len(classic_score.violations)


def run_episode_delegated(case, scenario):
    from ioabench.v5.core.engine import run_episode
    auxiliary = scenario.reference_auxiliary()
    return asyncio.run(run_episode(case, scenario, _policy_for(case, scenario), PROFILE,
                                   parameters={"temperature": 0.0}, auxiliary=auxiliary))


def _policy_for(case, scenario):
    from ioabench.v5.core.policy import ScriptedPolicyModel
    classic = load(case.suite_id[:4])
    return classic.policies()["witness"]


@pytest.mark.parametrize("sid,kind", [("T361", "upstream_escalation_delivered"),
                                      ("T362", "mass_report_alert_delivered"),
                                      ("T363", "platform_default_flipped")])
def test_dynamic_delivery_event_fires_mid_episode(sid: str, kind: str) -> None:
    module = __import__(f"ioabench.v5.dynamic.{sid.lower()}_slice", fromlist=["generate"])
    _, risk = module.generate(seed=5, families=1)[0]
    scenario = (module.T361DynamicScenario() if sid == "T361" else
                module.T362DynamicScenario() if sid == "T362" else
                module.T363DynamicScenario())
    from ioabench.v5.core.engine import run_episode
    auxiliary = scenario.reference_auxiliary()
    trace = asyncio.run(run_episode(risk, scenario, _policy_for(risk, scenario), PROFILE,
                                    parameters={"temperature": 0.0}, auxiliary=auxiliary))
    events = [e for e in trace.events if e["kind"] == kind]
    assert len(events) == 1 and events[0]["turn"] >= 1
    assert ledger_integrity(trace)["passed"]


def test_simulation_slices_are_signature_distinct_and_marked() -> None:
    from ioabench.v5.dynamic.t361_slice import generate as g361
    from ioabench.v5.dynamic.t362_slice import generate as g362
    from ioabench.v5.dynamic.t363_slice import generate as g363
    c361, r361 = g361(seed=5, families=1)[0]
    c362, r362 = g362(seed=5, families=1)[0]
    c363, r363 = g363(seed=5, families=1)[0]
    for a, b in ((c361, c362), (c361, c363), (c362, c363)):
        assert structural_delta(signature(a.as_dict()), signature(b.as_dict()))["dimensions"]
    for case in (c361, c362, c363):
        assert case.provenance.get("simulation_only") is True
        assert case.simulation_only  # exact registered dynamic identities retain the boundary
    for sid in ("T361", "T362", "T363"):
        classic = load(sid).generate(seed=5, families=1)[0][0].as_dict()
        slice_case = {"T361": c361, "T362": c362, "T363": c363}[sid].as_dict()
        assert structural_delta(signature(slice_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    import ioabench.v5.dynamic.t361_slice as m361
    import ioabench.v5.dynamic.t362_slice as m362
    import ioabench.v5.dynamic.t363_slice as m363
    c361, r361 = m361.generate(seed=5, families=1)[0]
    c362, r362 = m362.generate(seed=5, families=1)[0]
    c363, r363 = m363.generate(seed=5, families=1)[0]
    assert m361.fine_arm_delta(c361, r361) == []
    assert m362.fine_arm_delta(c362, r362) == []
    assert m363.fine_arm_delta(c363, r363) == []
    drifted = copy.deepcopy(r361)
    drifted.world["upstream_escalation"]["item_id"] = "different-item"
    assert any("same wrong item" in p for p in m361.fine_arm_delta(c361, drifted))
    drifted2 = copy.deepcopy(r363)
    drifted2.world["platform_flip"]["second_phase"] = drifted2.world["platform_setting"]
    assert any("no flip" in p for p in m363.fine_arm_delta(c363, drifted2))


def ledger_integrity(trace):
    from ioabench.v5.core.monitor import ledger_integrity as li
    return li(trace)

