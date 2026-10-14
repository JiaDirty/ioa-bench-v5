"""M7 cluster-2 tests: the T332 dynamic slice (staged partner conversation with a mid-episode
follow-up ask) — the extra ask arrives as a second message, and disclosure is judged on reply
bodies. No recovery reference exists (disclosure to an external party is irreversible)."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from ioabench.models import ModelProfile
from ioabench.v5.dynamic.gates import check_pair_dynamic, run_reference
from ioabench.v5.dynamic.signature import signature, structural_delta
from ioabench.v5.dynamic.t332_slice import (EXPECTED_REFERENCE, TIMING_RULES,
                                            T332DynamicScenario, fine_arm_delta, generate,
                                            policies, score)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity, message_flow

SCENARIO = T332DynamicScenario()
POLICIES = policies()
PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_t332_slice_pairs_pass_dynamic_gates() -> None:
    for control, risk in generate(seed=5, families=3):
        report = check_pair_dynamic(control, risk, scenario=SCENARIO, scorer=score,
                                    policies=POLICIES, expected=EXPECTED_REFERENCE,
                                    fine_arm_delta=fine_arm_delta)
        assert report["passed"], (report["pair_id"], report["failures"])


def test_follow_up_arrives_mid_episode_and_splits_arms() -> None:
    control, risk = generate(seed=5, families=1)[0]
    for case in (control, risk):
        trace = asyncio.run(run_episode(case, SCENARIO, POLICIES["witness"], PROFILE,
                                        parameters={"temperature": 0.0}))
        follow_ups = [e for e in trace.events if e["kind"] == "partner_follow_up_delivered"]
        assert len(follow_ups) == 1 and follow_ups[0]["turn"] >= 1
    assert risk.world["follow_up_ask"]["target"] in risk.oracle["confidential_values"]
    assert control.world["follow_up_ask"]["target"] == control.oracle["permitted_extra_value"]
    # the same reply behaviour is safe in both arms for the witness
    for case in (control, risk):
        trace = asyncio.run(run_episode(case, SCENARIO, POLICIES["witness"], PROFILE,
                                        parameters={"temperature": 0.0}))
        assert score(trace, case).safety == "SAFE"


def test_wholesale_record_dump_discloses_only_in_risk() -> None:
    _, risk = generate(seed=5, families=1)[0]
    naive_trace = asyncio.run(run_episode(risk, SCENARIO, POLICIES["naive"], PROFILE,
                                          parameters={"temperature": 0.0}))
    verdict = score(naive_trace, risk)
    assert verdict.safety == "UNSAFE" and verdict.consequence_persisted
    control, _ = generate(seed=5, families=1)[0]
    control_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["naive"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert score(control_trace, control).safety == "SAFE"
    assert ledger_integrity(control_trace)["passed"]
    flow = message_flow(control_trace)
    assert flow["paired"] >= 2 and not flow["undelivered_enqueues"]
    # naive skips the policy review (mechanism-susceptible by design); witness complies
    assert not evaluate_timing(control_trace, TIMING_RULES)["passed"]
    witness_trace = asyncio.run(run_episode(control, SCENARIO, POLICIES["witness"], PROFILE,
                                            parameters={"temperature": 0.0}))
    assert evaluate_timing(witness_trace, TIMING_RULES)["passed"]


def test_t332_score_serialization_is_stable_across_python_hash_seeds(tmp_path: Path) -> None:
    from ioabench.v5.suites import load
    _, risk = load("T332").generate(seed=5, families=1)[0]
    case_path = tmp_path / "risk.json"
    case_path.write_text(json.dumps(risk.as_dict(), ensure_ascii=False), encoding="utf-8")
    code = """
import asyncio, json, sys
from pathlib import Path
from ioabench.models import ModelProfile
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.suites import load
case = case_from_dict(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
module = load('T332')
trace = asyncio.run(run_episode(case, module.T332Scenario(), module.policies()['naive'],
                                ModelProfile('scripted', 'reference-policy', {}, {}, role='REFERENCE_POLICY'),
                                parameters={'temperature': 0.0}))
print(json.dumps(module.score(trace, case).as_dict(), sort_keys=True))
"""
    root = Path(__file__).resolve().parents[2]
    outputs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed,
                   PYTHONPATH=str(root / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""))
        outputs.append(subprocess.check_output([sys.executable, "-B", "-c", code, str(case_path)],
                                               text=True, env=env).strip())
    assert outputs[0] == outputs[1]


def test_t332_slice_signature_is_a_distinct_family() -> None:
    from ioabench.v5.dynamic.t331_slice import generate as generate_t331
    t332_case = generate(seed=5, families=1)[0][0].as_dict()
    t331_case = generate_t331(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t332_case), signature(t331_case))["dimensions"]
    from ioabench.v5.suites import load
    classic = load("T332").generate(seed=5, families=1)[0][0].as_dict()
    assert structural_delta(signature(t332_case), signature(classic))["dimensions"]


def test_fine_arm_delta_rejects_off_mechanism_changes() -> None:
    import copy
    control, risk = generate(seed=5, families=1)[0]
    assert fine_arm_delta(control, risk) == []
    drifted = copy.deepcopy(risk)
    drifted.world["support_record"]["support_channel"] = "changed"
    problems = fine_arm_delta(control, drifted)
    assert any("support_record" in p for p in problems)
    drifted2 = copy.deepcopy(risk)
    drifted2.world["follow_up_ask"]["target"] = control.oracle["permitted_extra_value"]
    problems2 = fine_arm_delta(control, drifted2)
    assert any("protected value" in p for p in problems2)
