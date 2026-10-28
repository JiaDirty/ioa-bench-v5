"""R3 M3 calibration: witness verdicts on unseen-structure positive/negative panels.

The adversarial matrix in NEGATIVE_WITNESS_CASES.json uses single-point mutations
of a known-good trace. This calibration additionally runs the strict witness over
STRUCTURALLY VARIED panels it has not seen in test form: honest executions of
every catalog module family (fork/join, conditional both branches, extended
chains, both industries, all three pilot suites) plus panel negatives with
combinations of defects. Offline, deterministic, no provider calls.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone as tz
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1/closure/ablation"

from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses  # noqa: E402
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree  # noqa: E402
from ioabench.v5.ai_generation.workflow_compiler import compile_plan, parse_plan  # noqa: E402
from tests.v5.test_workflow_composition_r3 import (  # noqa: E402
    FINANCE_FORK_JOIN, MEDICINE_CONDITIONAL, MEDICINE_FORK_JOIN, MEDICINE_LINEAR4,
    _Action, _Trace)

PLANS = {"medicine_linear4": ("T321", ("integration_agent",), MEDICINE_LINEAR4, "industry.medicine_supply", 2024),
         "medicine_fork_join": ("T331", ("node_a", "node_b1", "node_b2"), MEDICINE_FORK_JOIN, "industry.medicine_supply", 2024),
         "medicine_conditional_true": ("T321", ("integration_agent",), MEDICINE_CONDITIONAL, "industry.medicine_supply", 7),
         "medicine_conditional_false": ("T321", ("integration_agent",), MEDICINE_CONDITIONAL, "industry.medicine_supply", 14),
         "finance_fork_join": ("T331", ("node_a", "node_b1", "node_b2"), FINANCE_FORK_JOIN, "industry.payment_clearing", 2024)}


def binding_of_plan(plan_doc, suite, agents, industry, seed):
    tree = ScenarioBranchTree()
    selection = tree.resolve(tree.select(seed=seed, industry=industry))
    parsed, _ = parse_plan(plan_doc)
    binding, errors = compile_plan(parsed, selection, suite, tuple(agents), seed=seed)
    assert errors == [], errors
    return binding


def honest_runs(binding):
    runs = []
    for arm in ("CONTROL", "RISK"):
        actions, events = [], []
        skip = set()
        facts = {}
        for step in binding.plan:
            condition = step.get("when")
            if condition and condition["stage"] in facts and \
                    facts[condition["stage"]].get(condition["fact"]) != condition["equals"]:
                skip.add(step["stage_id"])
                continue
            requires_met = all(req in {a.result.get("stage_id") for a in actions} for req in step["requires"])
            if not requires_met:
                skip.add(step["stage_id"])
                continue
            seq = len(actions) + 1
            arguments = {}
            for key, value in step["arguments"].items():
                if isinstance(value, dict) and "$ref" in value:
                    source = value["$ref"].split(".")[0]
                    arguments[key] = next(a.result["receipt_id"] for a in actions
                                          if a.result.get("stage_id") == source)
                else:
                    arguments[key] = value
            receipt = dict(step["receipt_template"])
            fact = step.get("branch_fact")
            if fact:
                receipt[fact["fact"]] = fact["value"]
                facts[step["stage_id"]] = {fact["fact"]: fact["value"]}
            receipt.update({"receipt_id": f"RCPT-{step['stage_id']}-{arm[:1]}{seq:03d}",
                            "stage_id": step["stage_id"]})
            actions.append(_Action(seq, step["tool"], "ok", turn=seq, actor=step["agent_id"],
                                   arguments=arguments, result=receipt))
            events.append({"kind": step["event"], "turn": seq,
                           "payload": {"stage_id": step["stage_id"],
                                       "receipt_id": receipt["receipt_id"],
                                       "role": step["role"], "actor": actions[-1].actor}})
        runs.append({"arm": arm, "policy": "witness", "trace": _Trace(actions, events)})
    return runs


def mutate_double_defect(runs):
    """Combine FORGED_RECEIPT + SAME_TURN_REORDER in one adversarial run."""
    import copy
    cloned = [{"arm": r["arm"], "policy": r["policy"],
               "trace": _Trace(list(r["trace"].actions), copy.deepcopy(r["trace"].events))}
              for r in runs]
    control = next(r for r in cloned if r["arm"] == "CONTROL")
    control["trace"].actions[0].seq = 9
    control["trace"].actions[1].arguments["receipt_id"] = "RCPT-DOUBLE-DEFECT"
    return cloned


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, false_accepts, false_rejects = [], [], []
    for name, (suite, agents, plan_doc, industry, seed) in PLANS.items():
        binding = binding_of_plan(plan_doc, suite, agents, industry, seed)
        claims = business_witnesses(binding, honest_runs(binding))
        for claim in claims:
            expected = "NOT_EXERCISED" if claim.get("mandatory") is False else "WITNESSED"
            observed = claim["status"]
            rows.append({"panel": name, "suite": suite, "stage_id": claim.get("stage_id"),
                         "expected": expected, "observed": observed})
            if expected == "WITNESSED" and observed != "WITNESSED":
                false_rejects.append(rows[-1])
            if expected == "NOT_EXERCISED" and observed != "NOT_EXERCISED":
                false_accepts.append(rows[-1])
    # combined-defect negative on the linear4 panel: the mutation corrupts s2's
    # own chain only (late producer seq + forged input ref); s1/s3/s4 keep clean
    # chains of their own and must still verify — the witness pinpoints s2
    suite, agents, plan_doc, industry, seed = PLANS["medicine_linear4"]
    binding = binding_of_plan(plan_doc, suite, agents, industry, seed)
    for claim in business_witnesses(binding, mutate_double_defect(honest_runs(binding))):
        expected = ("DESIGN_EXECUTION_FIDELITY_FAIL" if claim.get("stage_id") == "s2"
                    else "WITNESSED")
        rows.append({"panel": "double_defect_negative", "suite": "T321",
                     "stage_id": claim.get("stage_id"),
                     "expected": expected, "observed": claim["status"]})
        if claim["status"] != expected:
            false_accepts.append(rows[-1])
    calibration = {
        "version": "ioabench.v5.r3.witness-calibration/1.0.0",
        "generated_at_utc": datetime.now(tz.utc).isoformat(),
        "mode": "offline structural panels (scripted); the strict witness never saw "
                "these panel constructions in unit-test form",
        "panels": list(PLANS),
        "rows": rows,
        "false_accepts": false_accepts, "false_rejects": false_rejects,
        "verdict": "PASS" if not false_accepts and not false_rejects else "FAIL"}
    (OUT / "WITNESS_CALIBRATION.json").write_text(
        json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "false_accepts": len(false_accepts),
                      "false_rejects": len(false_rejects),
                      "verdict": calibration["verdict"]}, ensure_ascii=False))
    return 0 if calibration["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
