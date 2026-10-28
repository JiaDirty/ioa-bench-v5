"""R2 M5 offline four-grid ablation: Tree on/off x IR on/off (zero provider calls).

Functional attribution only (05_实验与验收 C.3): which layer contributes the
business tool bindings, the business event DAG, and the illegal-input
interception. This is NOT an online causal yield comparison — routes with
different call structures are compared only at system level in AB_RESULTS.
"""
from __future__ import annotations

import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"

from ioabench.models import ModelProfile  # noqa: E402
from ioabench.v5.ai_generation.business_binding import BusinessBinding  # noqa: E402
from ioabench.v5.ai_generation.compiler_capabilities import validate_binding  # noqa: E402
from ioabench.v5.ai_generation.mechanism_ir import blueprint_from_ir, ir_from_blueprint  # noqa: E402
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec  # noqa: E402
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree  # noqa: E402
from ioabench.v5.ai_generation.tree_factory import assemble_blueprint  # noqa: E402
from ioabench.v5.core.engine import run_episode  # noqa: E402
from ioabench.v5.evaluation import atomic_json  # noqa: E402

SUITES = {
    "T331": {"target": {"rebroadcast_timing": "after_propagation"}, "seed": 311,
             "industry": "industry.medicine_supply"},
    "T321": {"target": {"close_gate": "profile_verified"}, "seed": 301,
             "industry": "industry.payment_clearing"},
    "T362": {"target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                        "evidence_release": "after_alert", "source_release": "per_owner_turn"},
             "seed": 321, "industry": "industry.medicine_supply"},
}

ILLEGAL_IR_MUTATIONS = ("zero_agents", "dependency_cycle", "dangling_evidence",
                        "cross_industry_tool")


def agents_for(spec, suite, target, seed, difficulty="M"):
    task = {"seed": seed, "difficulty": difficulty, "target": target, "subtype":
            {"T331": "T331-S5", "T321": "T321-S5", "T362": "T362-S1"}[suite]}
    blueprint = assemble_blueprint(spec, dict(target), task)
    pair = spec.adapter.compile_pair(blueprint, seed=seed)
    canonical = suite.split("-")[0]
    if canonical == "T331":
        return tuple(pair[0].world["chain"])
    if canonical == "T321":
        return ("integration_agent",)
    return ("moderator", "discussant_1", "discussant_2")


def business_events_of(binding, trace):
    names = {entry["event"] for entry in binding.event_dag} if binding else set()
    return sorted({event["kind"] for event in trace.events if event["kind"] in names})


async def measure(suite: str, tree: bool, ir: bool) -> dict:
    from ioabench.v5.ai_generation.tree_factory import _probe_compiled, candidate_ir
    spec = suite_spec(suite, typed=True)
    conf = SUITES[suite]
    seed, target, difficulty = conf["seed"], conf["target"], "M"
    binding = None
    if tree:
        selection = ScenarioBranchTree().select(seed=seed, industry=conf["industry"],
                                                obligations=())
        binding = BusinessBinding.compile(selection, suite, agents_for(spec, suite, target, seed))
    task = {"seed": seed, "difficulty": difficulty, "target": target, "subtype":
            {"T331": "T331-S5", "T321": "T321-S5", "T362": "T362-S1"}[suite],
            "assertions": []}
    if ir:
        payload = assemble_blueprint(spec, dict(target), task)["suite_payload"]
        ir_built = candidate_ir(spec, task, payload, binding, _probe_compiled(spec, task))
        blueprint = blueprint_from_ir(ir_built, binding, difficulty=difficulty)
    else:
        blueprint = assemble_blueprint(spec, dict(target), task)
        if binding is not None:
            blueprint = {**blueprint, "suite_payload": {**blueprint["suite_payload"],
                                                        "business_binding": binding.as_dict()}}
    compiled = await asyncio.to_thread(compile_and_gate, spec, blueprint, seed=seed)
    scenario = spec.scenario_factory()
    profile = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
    model = spec.policies["witness"]
    trace = await asyncio.to_thread(lambda: asyncio.run(
        run_episode(compiled["control"], scenario, model, profile,
                    parameters={"temperature": 0.0})))
    world = compiled["control"].world
    from ioabench.v5.dynamic.business_tools import business_grants
    return {"suite": suite, "tree": tree, "ir": ir,
            "gate_passed": compiled["gate"]["passed"],
            "world_has_binding": "business_binding" in world,
            "business_tools_granted": sorted(set(
                tool for agent in (world.get("chain") or ["integration_agent", "moderator",
                                                          "discussant_1", "discussant_2"])
                for tool in business_grants(world, agent))),
            "business_events_in_witness_trace": business_events_of(binding, trace),
            "workflow_hash": binding.canonical_workflow_hash if binding else None,
            "ir_validation_layer": ir}


def illegal_ir_rejections(suite: str) -> dict:
    """The IR layer must reject every illegal input BEFORE projection (R2-G2)."""
    spec = suite_spec(suite, typed=True)
    conf = SUITES[suite]
    base = assemble_blueprint(spec, dict(conf["target"]),
                              {"seed": conf["seed"], "difficulty": "M", "target": conf["target"],
                               "subtype": {"T331": "T331-S5", "T321": "T321-S5",
                                           "T362": "T362-S1"}[suite]})
    lifted = ir_from_blueprint(spec.suite_id, base)
    results = {}
    for mutation in ILLEGAL_IR_MUTATIONS:
        import dataclasses
        ir = lifted
        if mutation == "zero_agents":
            ir = dataclasses.replace(lifted, agents=())
        elif mutation == "dependency_cycle":
            events = lifted.typed_events or ()
            from ioabench.v5.ai_generation.mechanism_ir import IRDependency
            if len(events) >= 1:
                ir = dataclasses.replace(lifted, dependencies=(
                    IRDependency("forwarded", "upstream_rebroadcast_delivered", "happens_before"),
                    IRDependency("upstream_rebroadcast_delivered", "forwarded", "happens_before")))
            else:
                ir = dataclasses.replace(lifted, dependencies=(
                    IRDependency("x", "y", "happens_before"), IRDependency("y", "x", "happens_before")))
        elif mutation == "dangling_evidence":
            from ioabench.v5.ai_generation.mechanism_ir import IREvent
            events = tuple(lifted.typed_events) + (
                IREvent("dangling_event", next(iter(a.id for a in lifted.agents)), "act",
                        produces=("evidence.not_declared",)),)
            ir = dataclasses.replace(lifted, typed_events=events)
        else:  # cross_industry_tool via binding consistency
            other = "industry.payment_clearing" if conf["industry"] == "industry.medicine_supply" \
                else "industry.medicine_supply"
            agents = agents_for(spec, suite, conf["target"], conf["seed"])
            selection = ScenarioBranchTree().select(seed=conf["seed"], industry=other, obligations=())
            foreign = BusinessBinding.compile(selection, suite, agents)
            try:
                blueprint_from_ir(lifted, foreign, difficulty="M")
                results[mutation] = {"rejected": False}
                continue
            except ValueError:
                results[mutation] = {"rejected": True}
                continue
        try:
            blueprint_from_ir(ir, difficulty="M")
            results[mutation] = {"rejected": False}
        except ValueError:
            results[mutation] = {"rejected": True}
    return results


async def main() -> int:
    rows = []
    for suite in SUITES:
        for tree in (False, True):
            for ir in (False, True):
                rows.append(await measure(suite, tree, ir))
    interceptions = {suite: illegal_ir_rejections(suite) for suite in SUITES}
    csv_path = OUT / "ABLATION_OFFLINE.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["business_tools_granted"] = ";".join(row["business_tools_granted"])
            row["business_events_in_witness_trace"] = ";".join(row["business_events_in_witness_trace"])
            writer.writerow(row)
    report = {"version": "ioabench.v5.r2-offline-ablation/1.0.0",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "provider_calls": 0, "grid": rows,
              "illegal_input_interception": interceptions,
              "interpretation": "Tree supplies the consumed business tool/event layer; "
                                "IR supplies validation and illegal-input interception; "
                                "offline functional attribution only, not online yield causality"}
    atomic_json(OUT / "ABLATION_OFFLINE.json", report)
    ok = (all(row["gate_passed"] for row in rows)
          and all(row["world_has_binding"] == row["tree"] for row in rows)
          and all(bool(row["business_events_in_witness_trace"]) == row["tree"] for row in rows)
          and all(result["rejected"] for suite in interceptions
                  for result in interceptions[suite].values()))
    print(json.dumps({"ok": ok, "rows": len(rows),
                      "interceptions": {s: {m: r["rejected"] for m, r in v.items()}
                                        for s, v in interceptions.items()}}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
