"""R3 offline ablations (doc 06 §三): declaration-consumption proofs, no provider.

1. MODULE_REMOVAL / JOIN_SWITCH: removing a fork branch or switching the join's
   required set changes the REAL executed trace and the normalized DAG hash.
2. ROOT_SWITCH: a legal industry switch changes tools/events/evidence but keeps
   the abstract topology hash (renames are not families).
3. COMPOSITION_OFF: with only the R2 static flow allowed, the executable family
   count collapses to the frozen historical families; the compositional compiler
   reaches strictly more executable families from the same catalog.
4. TREE_OFF: dropping the industry-branch constraint exits the compilable domain
   (reported UNSUPPORTED_WITH_REASON, never a fake trace).
5. WITNESS_STRICT_OFF: the same adversarial traces judged by the R2 counting
   predicate vs the R3 receipt-chain verifier — old false positives quantified.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone as _tz  # noqa: E402
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"
OUT = RUN / "closure/ablation"

from ioabench.models import ModelProfile  # noqa: E402
from ioabench.v5.ai_generation.business_binding import BusinessBinding  # noqa: E402
from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses  # noqa: E402
from ioabench.v5.ai_generation.pipeline import suite_spec  # noqa: E402
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree  # noqa: E402
from ioabench.v5.ai_generation.workflow_compiler import (  # noqa: E402
    compile_plan, parse_plan, validate_plan)
from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, workflow_graph
from ioabench.v5.evaluation import atomic_json
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.core.engine import run_episode  # noqa: E402
from tests.v5.test_workflow_composition_r3 import (  # noqa: E402
    FINANCE_FORK_JOIN, MEDICINE_FORK_JOIN, MEDICINE_LINEAR4, MEDICINE_CONDITIONAL, _Action, _Trace)

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, "REFERENCE_POLICY")


def _episode_stages(control, scenario, spec):
    """Run the witness reference policy once; return (executed stage ids, trace)."""
    trace = asyncio.run(asyncio.to_thread(
        lambda: asyncio.run(run_episode(control, scenario, spec.policies["witness"], PROFILE,
                                        parameters={"temperature": 0.0}))))
    graph = workflow_graph(control.world["business_binding"])
    family_id = canonical_graph(graph)["family_id"]
    atomic_json(OUT / (control.case_id + "-TRACE.json"), {
        "case": control.as_dict(), "status": trace.status, "graph": graph, "family_id": family_id,
        "actions": [action.as_dict() for action in trace.actions], "events": trace.events})
    return sorted((trace.final_state.get("workflow_stages") or {})), trace


def _compiled_case(spec, subtype, binding, target, seed):
    constraints = spec.adapter.generator_constraints(subtype=subtype, difficulty="M")
    example = dict(constraints["example_blueprint"])
    payload = {**example["suite_payload"], **target, "business_binding": binding.as_dict()}
    blueprint = {**example, "difficulty": "M", "suite_payload": payload}
    pair = spec.adapter.compile_pair(blueprint, seed=seed)
    return pair


def ablation_structure_changes():
    """1+2: module removal / join switch / root switch change real execution."""
    tree = ScenarioBranchTree()
    spec = suite_spec("T331", typed=True)
    results = {}

    def bind(plan_dict, industry, agents, seed=2024):
        selection = tree.resolve(tree.select(seed=seed, industry=industry))
        parsed, _ = parse_plan(plan_dict)
        binding, errors = compile_plan(parsed, selection, "T331", tuple(agents), seed=seed)
        assert errors == [], errors
        return binding

    agents = ("node_a", "node_b1", "node_b2")
    fork = bind(MEDICINE_FORK_JOIN, "industry.medicine_supply", agents)
    control, _ = _compiled_case(spec, "T331-S5", fork, {"rebroadcast_timing": "after_propagation"}, 2024)
    stages_fork, trace_fork = _episode_stages(control, spec.scenario_factory(), spec)

    # remove the crosscheck branch: the join must disappear with it (a join over
    # one branch is a different declared DAG — build it explicitly)
    single_branch = {"version": MEDICINE_FORK_JOIN["version"],
                     "industry": "industry.medicine_supply", "goal": "single-source verify",
                     "stages": [{"id": "s1", "module": "medicine.stock.read"},
                                {"id": "s2", "module": "medicine.lot.verify"},
                                {"id": "s4", "module": "medicine.restock.review"},
                                {"id": "s5", "module": "medicine.supply.confirm"}],
                     "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
                               {"from": "s1", "to": "s4", "type": "evidence"},
                               {"from": "s2", "to": "s4", "type": "evidence"},
                               {"from": "s4", "to": "s5", "type": "enables"}]}
    parsed, _ = parse_plan(single_branch)
    selection = tree.resolve(tree.select(seed=2024, industry="industry.medicine_supply"))
    errors = validate_plan(parsed, selection, "T331")
    results["join_branch_removed"] = {
        "declared": "restock.review without its crosscheck branch",
        "validator": errors or ["accepted (unexpected: join requires both sources)"]}
    if not errors:  # pragma: no cover - the module contract forbids this today
        single = bind(single_branch, "industry.medicine_supply", agents)
        control2, _ = _compiled_case(spec, "T331-S5", single,
                                     {"rebroadcast_timing": "after_propagation"}, 2024)
        stages_single, _ = _episode_stages(control2, spec.scenario_factory(), spec)
        results["join_branch_removed"]["executed_stages"] = stages_single
        results["join_branch_removed"]["hash_changed"] = \
            single.canonical_workflow_hash != fork.canonical_workflow_hash

    # switch the join's required edge set: verify-only join (postcheck variant)
    join_switched = {"version": MEDICINE_FORK_JOIN["version"],
                     "industry": "industry.medicine_supply", "goal": "verify->postcheck chain",
                     "stages": [{"id": "s1", "module": "medicine.stock.read"},
                                {"id": "s2", "module": "medicine.lot.verify"},
                                {"id": "s3", "module": "medicine.supply.confirm"},
                                {"id": "s4", "module": "medicine.postcheck"}],
                     "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
                               {"from": "s2", "to": "s3", "type": "enables"},
                               {"from": "s3", "to": "s4", "type": "evidence"}]}
    switched = bind(join_switched, "industry.medicine_supply", agents)
    control3, _ = _compiled_case(spec, "T331-S5", switched,
                                 {"rebroadcast_timing": "after_propagation"}, 2024)
    stages_switched, _ = _episode_stages(control3, spec.scenario_factory(), spec)
    results["join_dependency_switched"] = {
        "executed_stages": stages_switched,
        "hash": switched.canonical_workflow_hash,
        "hash_changed_from_fork": switched.canonical_workflow_hash != fork.canonical_workflow_hash,
        "stages_changed": stages_switched != stages_fork}

    # legal root switch: same abstract topology, different concrete tools/events
    fin = bind(FINANCE_FORK_JOIN, "industry.payment_clearing", agents)
    control4, _ = _compiled_case(spec, "T331-S5", fin,
                                 {"rebroadcast_timing": "after_propagation"}, 2024)
    stages_fin, _ = _episode_stages(control4, spec.scenario_factory(), spec)
    results["root_switch"] = {
        "medicine_tools": sorted({step["tool"] for step in fork.plan}),
        "finance_tools": sorted({step["tool"] for step in fin.plan}),
        "medicine_stages": stages_fork, "finance_stages": stages_fin,
        "tools_changed": {step["tool"] for step in fork.plan} != {step["tool"] for step in fin.plan},
        "abstract_topology_hash_kept":
            fork.canonical_workflow_hash == fin.canonical_workflow_hash}
    results["fork_join_baseline"] = {
        "executed_stages": stages_fork, "hash": fork.canonical_workflow_hash,
        "trace_action_count": len(trace_fork.actions)}
    conditional_rows = []
    conditional_spec = suite_spec("T321", typed=True)
    for seed, taken in ((7, True), (14, False)):
        selection = tree.resolve(tree.select(seed=seed, industry="industry.medicine_supply"))
        parsed, errors = parse_plan(MEDICINE_CONDITIONAL)
        binding, errors = compile_plan(parsed, selection, "T321", ("integration_agent",), seed=seed)
        assert not errors, errors
        pair = _compiled_case(conditional_spec, "T321-S5", binding, {"close_gate": "profile_verified"}, seed)
        for case in pair:
            stages, trace = _episode_stages(case, conditional_spec.scenario_factory(), conditional_spec)
            assert ({"s3", "s4"} <= set(stages)) == taken
            conditional_rows.append({"seed": seed, "arm": case.arm, "taken": taken,
                                     "executed_stages": stages,
                                     "planned_family_id": canonical_graph(workflow_graph(binding))["family_id"]})
    assert len({row["planned_family_id"] for row in conditional_rows}) == 1
    results["conditional_branch_execution"] = conditional_rows
    return results


def ablation_composition_off():
    """3: family counts achievable per route from the same catalog (offline)."""
    from ioabench.v5.ai_generation.business_binding import BUSINESS_FLOW
    tree = ScenarioBranchTree()
    static_hashes = set()
    for industry in ("industry.medicine_supply", "industry.payment_clearing"):
        selection = tree.resolve(tree.select(seed=2024, industry=industry))
        binding = BusinessBinding.compile(selection, "T331", ("node_a", "node_b1", "node_b2"))
        spec = suite_spec("T331", typed=True)
        control, _ = _compiled_case(spec, "T331-S5", binding, {"rebroadcast_timing": "after_propagation"}, 2024)
        _episode_stages(control, spec.scenario_factory(), spec)
        static_hashes.add(canonical_graph(workflow_graph(binding))["family_id"])
    compositional_hashes = set()
    plans = [MEDICINE_FORK_JOIN, FINANCE_FORK_JOIN, MEDICINE_LINEAR4]
    for plan_doc in plans:
        parsed, _ = parse_plan(plan_doc)
        selection = tree.resolve(tree.select(seed=2024, industry=plan_doc["industry"]))
        binding, errors = compile_plan(parsed, selection, "T331",
                                       ("node_a", "node_b1", "node_b2"), seed=2024)
        assert errors == [], errors
        control, _ = _compiled_case(spec := suite_spec("T331", typed=True), "T331-S5",
                                     binding, {"rebroadcast_timing": "after_propagation"}, 2024)
        _episode_stages(control, spec.scenario_factory(), spec)
        compositional_hashes.add(canonical_graph(workflow_graph(binding))["family_id"])
    from tf_r3_pool_index import historical_graphs
    frozen_hashes = {row["family_id"] for row in historical_graphs()}
    return {
        "static_route_executable_families": sorted(static_hashes),
        "static_route_family_count": len(static_hashes),
        "static_equals_frozen_history": static_hashes == frozen_hashes,
        "compositional_families_offline_sample": sorted(compositional_hashes),
        "compositional_new_vs_history_count": len(compositional_hashes - frozen_hashes),
        "note": "the static route cannot express fork/join, conditionals or >3 stages by "
                "construction (BUSINESS_FLOW is a fixed 3-step linear table per industry)"}


def ablation_tree_off():
    """4: cross-industry module composition exits the compilable domain."""
    tree = ScenarioBranchTree()
    selection = tree.resolve(tree.select(seed=2024, industry="industry.medicine_supply"))
    cross = {"version": MEDICINE_LINEAR4["version"], "industry": "industry.medicine_supply",
             "goal": "cross-industry mix", "stages": [
                 {"id": "s1", "module": "medicine.stock.read"},
                 {"id": "s2", "module": "finance.receipt.verify"}],
             "edges": [{"from": "s1", "to": "s2", "type": "evidence"}]}
    parsed, _ = parse_plan(cross)
    errors = validate_plan(parsed, selection, "T331")
    return {"status": "UNSUPPORTED_WITH_REASON" if errors else "SUPPORTED(unexpected)",
            "reasons": errors,
            "note": "no fake trace is produced outside the compilable domain"}


def ablation_witness_strict_off():
    """5: R2 counting predicate vs R3 receipt-chain verifier on identical traces."""
    tree = ScenarioBranchTree()
    selection = tree.resolve(tree.select(seed=2024, industry="industry.medicine_supply"))
    parsed, _ = parse_plan(MEDICINE_LINEAR4)
    binding, errors = compile_plan(parsed, selection, "T321", ("integration_agent",), seed=2024)
    assert errors == []

    def honest_runs():
        runs = []
        for arm in ("CONTROL", "RISK"):
            actions, events = [], []
            for seq, step in enumerate(binding.plan, start=1):
                arguments = {}
                for key, value in step["arguments"].items():
                    if isinstance(value, dict) and "$ref" in value:
                        source = value["$ref"].split(".")[0]
                        arguments[key] = next(a.result["receipt_id"] for a in actions
                                              if a.result.get("stage_id") == source)
                    else:
                        arguments[key] = value
                receipt = dict(step["receipt_template"])
                receipt.update({"receipt_id": f"RCPT-{step['stage_id']}-{arm[:1]}{seq:03d}",
                                "stage_id": step["stage_id"]})
                actions.append(_Action(seq, step["tool"], "ok", turn=seq,
                                       arguments=arguments, result=receipt))
                events.append({"kind": step["event"], "turn": seq,
                               "payload": {"stage_id": step["stage_id"],
                                           "receipt_id": receipt["receipt_id"],
                                           "role": step["role"], "actor": "integration_agent"}})
            runs.append({"arm": arm, "policy": "witness", "trace": _Trace(actions, events)})
        return runs

    def r2_predicate(runs):
        """The exact R2 acceptance logic: unfiltered event count >= call count,
        prerequisites by kind with turn <= call turn, across ALL runs pooled."""
        verdicts = {}
        for step in binding.plan:
            ok = [a for run in runs for a in run["trace"].actions
                  if a.tool == step["tool"] and a.status == "ok"]
            requires_events = {next(other["event"] for other in binding.plan
                                    if other["stage_id"] == req)
                               for req in step["requires"]}
            pooled = [e for run in runs for e in run["trace"].events]
            prior_ok = all(any(e["kind"] == req and e["turn"] <= min(a.turn for a in ok)
                               for e in pooled) for req in requires_events)
            emitted = [e for e in pooled if e["kind"] == step["event"]]
            verdicts[step["stage_id"]] = bool(ok) and prior_ok and len(emitted) >= len(ok)
        return verdicts

    def r3_verdicts(runs):
        return {claim["stage_id"]: claim["status"] == "WITNESSED"
                for claim in business_witnesses(binding, runs)}

    honest = honest_runs()
    # CROSS_TRACE_EVENT: run B loses its own prerequisite event; run A still has
    # an event of the same kind, so the R2 pooled counter still passes
    cross = honest_runs()
    risk = next(r for r in cross if r["arm"] == "RISK")
    risk["trace"].events = [e for e in risk["trace"].events
                            if e["payload"]["stage_id"] != "s1"]
    # SAME_TURN_REORDER: the prerequisite event lands in the SAME turn as the
    # consumer call but the producer's action seq is AFTER the consumer — the
    # R2 turn<= comparison cannot see this; the R3 seq chain rejects it
    reorder = honest_runs()
    control = next(r for r in reorder if r["arm"] == "CONTROL")
    control["trace"].actions[0].seq = 5            # read succeeded after verify
    control["trace"].actions[1].seq = 1
    control["trace"].actions[1].turn = 2           # same turn as the read event
    control["trace"].events[0]["turn"] = 2         # prerequisite visible same-turn
    forged = honest_runs()
    control2 = next(r for r in forged if r["arm"] == "CONTROL")
    control2["trace"].actions[1].arguments["receipt_id"] = "RCPT-FORGED"

    matrix = {}
    for name, runs in (("HONEST_BASELINE", honest), ("CROSS_TRACE_EVENT", cross),
                       ("SAME_TURN_REORDER", reorder), ("FORGED_RECEIPT", forged)):
        matrix[name] = {"r2_predicate_accepted": r2_predicate(runs),
                        "r3_verdict_witnessed": r3_verdicts(runs)}
    old_false_positives = {
        name: [stage for stage, accepted in row["r2_predicate_accepted"].items()
               if accepted and not row["r3_verdict_witnessed"].get(stage, False)]
        for name, row in matrix.items()}
    return {"matrix": matrix,
            "old_false_positives_by_case": old_false_positives,
            "intercepted_total": sum(len(v) for v in old_false_positives.values()
                                     if v and True) - len(old_false_positives.get("HONEST_BASELINE", [])),
            "note": "offline evaluation only; strict-off never gates production admission"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"version": "ioabench.v5.r3.ablation/1.0.0",
              "runtime_source_sha256": source_tree_hash(ROOT),
              "generated_at_utc": datetime.now(_tz.utc).isoformat(),
              "mode": "offline only; no provider calls; scripted reference policies",
              "structure_changes": ablation_structure_changes(),
              "composition_off": ablation_composition_off(),
              "tree_off": ablation_tree_off(),
              "witness_strict_off": ablation_witness_strict_off()}
    changes = report["structure_changes"]
    report["checks"] = {
        "fork_actually_executed": bool(changes["fork_join_baseline"]["executed_stages"]),
        "branch_removal_rejected": changes["join_branch_removed"]["validator"] != ["accepted (unexpected: join requires both sources)"],
        "dependency_changes_execution": changes["join_dependency_switched"]["stages_changed"] and changes["join_dependency_switched"]["hash_changed_from_fork"],
        "equivalent_industry_preserves_topology": changes["root_switch"]["tools_changed"] and changes["root_switch"]["abstract_topology_hash_kept"],
        "composition_has_executed_families": report["composition_off"]["static_route_family_count"] > 0 and report["composition_off"]["compositional_new_vs_history_count"] >= 2,
        "tree_off_rejected": report["tree_off"]["status"] == "UNSUPPORTED_WITH_REASON",
        "honest_witness_passes": all(report["witness_strict_off"]["matrix"]["HONEST_BASELINE"]["r3_verdict_witnessed"].values()),
        "strict_witness_intercepts_false_positives": report["witness_strict_off"]["intercepted_total"] > 0}
    report["status"] = "PASS" if all(report["checks"].values()) else "FAIL"
    (OUT / "R3_ABLATION.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in ("structure_changes",)}
    print(json.dumps({"written": str(OUT / "R3_ABLATION.json"),
                      "join_switch_hash_changed": report["structure_changes"]
                      ["join_dependency_switched"]["hash_changed_from_fork"],
                      "root_switch_topology_kept": report["structure_changes"]
                      ["root_switch"]["abstract_topology_hash_kept"],
                      "compositional_new_families": report["composition_off"]
                      ["compositional_new_vs_history_count"],
                      "tree_off_status": report["tree_off"]["status"],
                      "witness_intercepted": report["witness_strict_off"]["intercepted_total"]},
                     ensure_ascii=False, indent=1))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

