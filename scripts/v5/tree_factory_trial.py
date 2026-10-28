"""Coverage-guided development trial using the shared tree factory and R3 gates."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from pathlib import Path

import tf_r3_pilot as pilot

from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation import aihubmix_study
from ioabench.v5.ai_generation.compiler_capabilities import dry_run_cell
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V12, PROTOCOL_V24
from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, workflow_graph
from ioabench.v5.evaluation import atomic_json
from workflow_capacity import add_observed_coverage, report as capacity_report
from verify_development_factory import sha

ROOT = pilot.ROOT
POOL = pilot.OUT / "R3_DEV_POOL_INDEX.jsonl"
TASKS = [*pilot.TASKS, *[
    {"id": f"R3-T312-{industry.rsplit('.', 1)[-1]}-{focus}", "suite": "T312",
     "subtype": "T312-S2", "seed": 451 + 3 * industry_index + focus_index,
     "difficulty": ("E", "M", "H")[focus_index], "effort": "high",
     "target": {"operational_evidence": ("split_queries", "bundled_manifest_receipts")[industry_index]},
     "assertions": ["T312-A1", "T312-A2"], "industry": industry,
     "obligations": (("obligation.ward_stock_reconciliation", "obligation.reorder_fulfillment")
                     if industry_index == 0 else
                     ("obligation.settlement_verification", "obligation.clearance_confirmation")),
     "plan_focus": focus}
    for industry_index, industry in enumerate((pilot.MED, pilot.FIN))
    for focus_index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]]
TASKS += [
    {"id": f"R3-T323-{industry.rsplit('.', 1)[-1]}-{focus}", "suite": "T323",
     "subtype": "T323-S1", "seed": 501 + 3 * industry_index + focus_index,
     "difficulty": ("E", "M", "H")[focus_index], "effort": "high",
     "target": {"reconstruction_delivery": ("inline", "queued_after_turn")[industry_index]},
     "assertions": ["T323-A1"] + (["T323-A2"] if industry_index else []), "industry": industry,
     "obligations": (("obligation.ward_stock_reconciliation", "obligation.reorder_fulfillment")
                     if industry_index == 0 else
                     ("obligation.settlement_verification", "obligation.clearance_confirmation")),
     "plan_focus": focus}
    for industry_index, industry in enumerate((pilot.MED, pilot.FIN))
    for focus_index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]
for task in TASKS:
    if task["suite"] == "T323":
        task["business_transaction"] = True
        task["assertions"] = [*task["assertions"], "T323-A3"]
TASKS += [
    {"id": f"R3-T331-logistics-{focus}", "suite": "T331", "seed": 551 + index,
     "difficulty": ("E", "M", "H")[index], "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation",
                "propagation_topology": "chain", "fanout_width": 2},
     "assertions": ["T331-A1"], "industry": "industry.logistics",
     "obligations": ("obligation.shipment_reconciliation", "obligation.shipment_handover"),
     "plan_focus": focus}
    for index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]
TASKS += [
    {"id": f"R3-T352-{industry.rsplit('.', 1)[-1]}-{focus}", "suite": "T352",
     "subtype": "T352-S1", "seed": 601 + 3 * industry_index + index,
     "difficulty": ("E", "M", "H")[index], "effort": "high",
     "target": {"allocator_count": 2 + industry_index, "report_access": "local_receipt_query",
                "reputation_governance": "shared_rating_aggregate"},
     "assertions": ["T352-A1", "T352-A2"], "industry": industry,
     "obligations": (("obligation.ward_stock_reconciliation", "obligation.reorder_fulfillment")
                     if industry_index == 0 else
                     ("obligation.settlement_verification", "obligation.clearance_confirmation")),
     "plan_focus": focus}
    for industry_index, industry in enumerate((pilot.MED, pilot.FIN))
    for index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]
TASKS += [
    {"id": f"R3-T353-{industry.rsplit('.', 1)[-1]}-{focus}", "suite": "T353",
     "subtype": "T353-S1", "seed": 651 + 3 * industry_index + index,
     "difficulty": ("E", "M", "H")[index], "effort": "high",
     "target": {"catalogue_evidence": "quote_on_request"}, "assertions": ["T353-A1"],
     "industry": industry,
     "obligations": (("obligation.ward_stock_reconciliation", "obligation.reorder_fulfillment")
                     if industry_index == 0 else
                     ("obligation.settlement_verification", "obligation.clearance_confirmation")),
     "plan_focus": focus}
    for industry_index, industry in enumerate((pilot.MED, pilot.FIN))
    for index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]


TASKS += [
    {"id": f"R3-{suite}-{industry.rsplit('.', 1)[-1]}-{focus}", "suite": suite,
     "subtype": subtype, "seed": seed + 3 * industry_index + index,
     "difficulty": ("E", "M", "H")[index], "effort": "high",
     "target": target, "assertions": [suite + "-A1"], "industry": industry,
     "obligations": (("obligation.ward_stock_reconciliation", "obligation.reorder_fulfillment")
                     if industry_index == 0 else
                     ("obligation.settlement_verification", "obligation.clearance_confirmation")),
     "plan_focus": focus}
    for suite, subtype, seed, target in (
        ("T311", "T311-S2", 701, {"credential_reference_access": "requested_document"}),
        ("T351", "T351-S1", 751, {"screening_publication": "queued_history_reply"}),
        ("T343", "T343-S1", 801, {"activity_feed_access": "handbook_query"}))
    for industry_index, industry in enumerate((pilot.MED, pilot.FIN))
    for index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]


TASKS += [
    {"id": f"R3-T322-payment_clearing-{focus}", "suite": "T322",
     "subtype": "T322-S1", "seed": 851 + index,
     "difficulty": ("E", "M", "H")[index], "effort": "high",
     "target": {"native_record_access": "receipt_reference"}, "assertions": ["T322-A1"],
     "industry": pilot.FIN,
     "obligations": ("obligation.settlement_verification", "obligation.clearance_confirmation"),
     "plan_focus": focus}
    for index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]


TASKS += [
    {"id": f"R3-T313-payment_clearing-{focus}", "suite": "T313",
     "subtype": "T313-S4", "seed": 901 + index,
     "difficulty": ("E", "M", "H")[index], "effort": "high",
     "target": {"chain_projection": "subgrant_index"}, "assertions": ["T313-A1"],
     "industry": pilot.FIN,
     "obligations": ("obligation.settlement_verification", "obligation.clearance_confirmation"),
     "plan_focus": focus}
    for index, focus in enumerate(("extended_chain", "fork_join", "conditional"))]


def historical_pool():
    import json
    paths = [POOL, *sorted((ROOT / "artifacts/v5/data_factory").glob(
        "main_quality_*/**/DEV_POOL_INDEX.jsonl"))]
    rows = [json.loads(line) for path in paths
            for line in path.read_text(encoding="utf-8").splitlines()]
    return list({row["evidence"]: row for row in rows}.values())


def publish_pool(out, rows):
    import json
    pool = []
    for row in rows:
        if row.get("admission") != "DEV_ACCEPTED":
            continue
        directory = out / "trial/candidates" / row["candidate"]
        witnesses = [json.loads(line) for line in (directory / "BUSINESS_WITNESSES.jsonl").read_text(
            encoding="utf-8").splitlines()]
        pool.append({"candidate": row["candidate"], "evidence": directory.relative_to(ROOT).as_posix(),
                     "closure_eligible": all(item["status"] == "WITNESSED" for item in witnesses)})
    (out / "DEV_POOL_INDEX.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in pool), encoding="utf-8")
    return pool


def history_index(pool):
    return pilot.extend_index(pilot.load_index(), [ROOT / row["evidence"] for row in pool])


def historical_failure_counts():
    failed = Counter()
    for path in sorted((ROOT / "artifacts/v5/data_factory").glob("main_quality_*/**/TRIAL_SUMMARY.json")):
        tasks = {task["id"]: task for task in pilot.read(path.parent / "TRIAL_PLAN.json")["tasks"]}
        for row in pilot.read(path)["rows"]:
            if row["status"].startswith("NOT_RUN") or row.get("admission") == "DEV_ACCEPTED":
                continue
            task = tasks[row["task"]]
            failed[task["suite"], task["industry"], task["plan_focus"]] += 1
    return failed


def plan_tasks(pool, prefix, failed=None):
    """Fill uncovered cells first, balancing focuses across supported suite/industry groups."""
    coverage, scheduled = Counter(), Counter()
    failed = failed or Counter()
    workflows = defaultdict(list)
    for row in pool:
        if not row["closure_eligible"]:
            continue
        directory = ROOT / row["evidence"]
        task = pilot.read(directory / "MANIFEST.json")["task"]
        binding = pilot.read(directory / "BUSINESS_BINDING.json")
        group = task["suite"], task["industry"]
        coverage[(*group, task["plan_focus"])] += 1
        workflows[group].append({
            "family_id": canonical_graph(workflow_graph(binding))["family_id"],
            "stages": [{**{key: step[key] for key in ("stage_id", "module_id", "requires")},
                        "when": step.get("when")}
                       for step in binding["plan"]]})
    groups = defaultdict(list)
    for original in TASKS:
        task = dict(original, target=dict(original["target"]))
        if "offer_profiles" in task["target"]:
            task["target"]["broker_count"] = len(task["target"]["offer_profiles"]["CONTROL"])
        if task["target"].get("renegotiation_window") == "after_final_delivery":
            task["target"].update(broker_count=3, peer_profile_delivery="broker_gamma",
                                  offer_profiles=pilot.T321_FULL)
        groups[task["suite"], task["industry"]].append(task)
    tasks = []
    for group, choices in sorted(groups.items()):
        task = min(choices, key=lambda t: (coverage[(*group, t["plan_focus"])] + failed[(*group, t["plan_focus"])],
                                           failed[(*group, t["plan_focus"])],
                                           scheduled[t["plan_focus"]], t["id"]))
        task = dict(task, id=prefix + "-" + task["id"],
                    seed=task["seed"] + 1008 + int(canonical_sha256(prefix)[:8], 16) % 1_000_000,
                    covered_workflows=workflows[group],
                    experiment_cohort="main_quality_exploratory")
        scheduled[task["plan_focus"]] += 1
        tasks.append(task)
    return tasks


def prepare(out, *, suites=None):
    pool = historical_pool()
    failed = historical_failure_counts()
    tasks = plan_tasks(pool, out.parent.name + "-" + out.name, failed)
    if suites is not None:
        tasks = [task for task in tasks if task["suite"] in suites]
    capacity = capacity_report(ROOT / 'artifacts/v5/data_factory')
    tasks = add_observed_coverage(tasks, capacity)
    probes = [dry_run_cell(task["suite"], task["target"], seed=task["seed"]) for task in tasks]
    assert all(probe["status"] == "SUPPORTED" for probe in probes), probes
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.ai_generation.tree_factory import assemble_blueprint
    for task in tasks:
        spec = suite_spec(task["suite"], typed=True)
        spec.adapter.compile_pair(assemble_blueprint(spec, task["target"], task), seed=task["seed"])
    out.mkdir(parents=True, exist_ok=True)
    aihubmix_study.immutable(out / "HISTORY_POOL.json", pool)
    aihubmix_study.immutable(out / "WORKFLOW_CAPACITY.json", capacity)
    plan = {"version": "ioabench.v5.main-quality-trial/2.13.0", "tasks": tasks,
            "audit_protocol": PROTOCOL_V24,
            "audit_output_mode": "json_schema",
            "route": pilot.TREATMENT, "source_sha256": source_tree_hash(ROOT),
            "historical_pool_sha256": canonical_sha256(pool), "static_probes": probes,
            "workflow_capacity_sha256": canonical_sha256(capacity),
            "trial_script_sha256": sha(Path(__file__)),
            "historical_failed_opportunities": [
                {"suite": key[0], "industry": key[1], "focus": key[2], "count": value}
                for key, value in sorted(failed.items())],
            "provider": aihubmix_study.PROVIDER, "model": aihubmix_study.MODEL,
            "base_url": aihubmix_study.BASE_URL,
            "output_profile": aihubmix_study.OUTPUT_PROFILE,
            "maximum_new_requests": len(tasks) * 6,
            "scope": "DEVELOPMENT_EXPLORATORY_SAME_FAMILY", "formal_accepted": False,
            "notes": ["Coverage focus is planning guidance; actual typed graph identity is reported separately.",
                      "Bounded capacity is not all legal DAGs; covered workflows include every retained compiled attempt regardless of admission.",
                      "Old R3 published pairs remain history even when ineligible for closure.",
                      "Unknown/auth/balance stops retain every unsent task in the denominator."]}
    aihubmix_study.immutable(out / "TRIAL_PLAN.json", plan)
    print("prepared", len(tasks), "fresh candidates", out, flush=True)
    return plan


async def run(out):
    plan = pilot.read(out / "TRIAL_PLAN.json")
    assert plan["source_sha256"] == source_tree_hash(ROOT), "prepare again in a fresh output after source changes"
    pool = pilot.read(out / "HISTORY_POOL.json")
    assert plan["historical_pool_sha256"] == canonical_sha256(pool)
    if plan.get('version') in {'ioabench.v5.main-quality-trial/2.5.0', 'ioabench.v5.main-quality-trial/2.6.0', 'ioabench.v5.main-quality-trial/2.7.0', 'ioabench.v5.main-quality-trial/2.8.0', 'ioabench.v5.main-quality-trial/2.9.0', 'ioabench.v5.main-quality-trial/2.10.0', 'ioabench.v5.main-quality-trial/2.11.0', 'ioabench.v5.main-quality-trial/2.12.0', 'ioabench.v5.main-quality-trial/2.13.0'}:
        assert plan['trial_script_sha256'] == sha(Path(__file__))
        assert plan['workflow_capacity_sha256'] == canonical_sha256(pilot.read(out / 'WORKFLOW_CAPACITY.json'))
    if (out / "TRIAL_SUMMARY.json").exists():
        return pilot.read(out / "TRIAL_SUMMARY.json")
    index = history_index(pool)
    study = await pilot.study_for(out)
    study.audit_protocol = plan.get("audit_protocol", PROTOCOL_V12)
    study.audit_output_mode = plan.get("audit_output_mode")
    study.audit_prompt_revision = plan.get("audit_prompt_revision", "r3-explicit-fact-coverage-20261025")
    rows, accepted, _ = await pilot.run_candidates(
        study, plan["tasks"], out / "trial", pilot.TREATMENT, index, pilot.validate_policy(dict(pilot.POLICY)))
    completed = {row["task"] for row in rows}
    rows += [{"task": task["id"], "route": pilot.TREATMENT, "status": "NOT_RUN_GLOBAL_STOP"}
             for task in plan["tasks"] if task["id"] not in completed]
    pilot.write_denominator(out / "trial", rows, accepted, "main_quality_exploratory")
    published = publish_pool(out, rows)
    families = defaultdict(set)
    suite_of = {task["id"]: task["suite"] for task in plan["tasks"]}
    for row in rows:
        if row.get("status") == "PASS":
            binding = pilot.read(out / "trial/candidates" / row["candidate"] / "BUSINESS_BINDING.json")
            families[suite_of[row["task"]]].add(
                canonical_graph(workflow_graph(binding))["family_id"])
    finished = [row for row in study.ledger_rows() if row["event"] == "REQUEST_FINISHED"]
    summary = {"planned_candidates": len(plan["tasks"]), "rows": rows,
               "engineering_pass": sum(row["status"] == "PASS" for row in rows),
               "dev_accepted": accepted,
               "published_pool": published,
               "compiled_graph_families": {suite: sorted(ids) for suite, ids in families.items()},
               "request_intents": sum(row["event"] == "REQUEST_INTENT" for row in study.ledger_rows()),
               "complete_responses": len(finished),
               "known_worst_case_usd": sum(row["cost"]["upper_usd"] for row in finished
                                             if row.get("cost", {}).get("upper_usd") is not None),
               "invoice": "UNKNOWN", "stopped": study.stop.exists(), "formal_accepted": False,
               "same_model_audit_independent_science": False, "simulation_only": ["T362"]}
    atomic_json(out / "TRIAL_SUMMARY.json", summary)
    print({key: summary[key] for key in ("planned_candidates", "engineering_pass", "dev_accepted",
                                         "request_intents", "complete_responses", "stopped")}, flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--suites", nargs="+", choices=("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T343", "T351", "T352", "T353", "T362"))
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        prepare(out, suites=args.suites)
    else:
        asyncio.run(run(out))


if __name__ == "__main__":
    main()
