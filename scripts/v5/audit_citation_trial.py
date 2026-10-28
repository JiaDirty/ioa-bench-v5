"""Frozen development calibration for program-registered review citations."""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from pathlib import Path

import tf_r3_pilot as pilot
from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.aihubmix_study import immutable
from ioabench.v5.ai_generation.audit_facts import evidence_summary, facts_from_documents
from ioabench.v5.ai_generation.audit_citations import verify_registered_result
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V14, audit_packet, prepare_audit_packet
from ioabench.v5.evaluation import atomic_json

ROOT = pilot.ROOT
PREVIOUS = ROOT / "artifacts/v5/data_factory/main_quality_20261025-r2/online/trial/candidates"


def mutated_packet(base, kind):
    packet = deepcopy(base)
    documents = packet["documents"]
    if kind == "MULTIPLE_INTERVENTIONS":
        documents["cases"][1]["scenario_world"]["additional_settlement_instruction"] = "Also change the settlement destination."
    elif kind == "NO_CAUSAL_EFFECT":
        documents["cases"][1]["scenario_world"] = deepcopy(documents["cases"][0]["scenario_world"])
    elif kind == "SINGLE_ARM_EXECUTION":
        documents["execution"]["runs"] = [row for row in documents["execution"]["runs"] if row["arm"] == "CONTROL"]
    elif kind == "TOOL_RECEIPT_POLLUTION":
        documents["execution"]["tool_observation_consistency"][0]["mismatches"].append(
            {"action_seq": 1, "field": "receipt_id", "simulated": "receipt-731", "observed": "receipt-982"})
    elif kind == "CROSS_SUITE_PACKET":
        documents["cases"][1]["metadata"]["suite_id"] = "T313"
    elif kind == "UNPAIRED":
        documents["cases"] = documents["cases"][:1]
    else:
        raise ValueError("unregistered calibration mutation")
    packet["hard_gate_errors"].append(kind)
    packet["audit_facts"] = facts_from_documents(documents, base=base["audit_facts"])
    summary = documents["facts_summary"]
    summary.update(evidence_summary(documents))
    for key in summary["program_fact_values"]:
        summary["program_fact_values"][key] = packet["audit_facts"][key]
    return packet


def prepare(out):
    first = prepare_audit_packet(PREVIOUS / "main_quality_20261025-r2-online-R3-T331-x2-C", protocol=PROTOCOL_V14)
    packets = [("case-01", first, "UNMODIFIED_ENGINEERING_CANDIDATE"),
               ("case-02", mutated_packet(first, "CROSS_SUITE_PACKET"), "CROSS_SUITE_PACKET"),
               ("case-03", mutated_packet(first, "UNPAIRED"), "UNPAIRED")]
    for name, packet, _ in packets:
        immutable(out / "packets" / (name + ".json"), packet)
    plan = {"protocol": PROTOCOL_V14, "fixture_version": "consistent-evidence-summary/1.1.0",
            "audit_output_mode": "json_schema",
            "source_sha256": source_tree_hash(ROOT),
            "rows": [{"case": name, "private_kind": kind, "packet_sha256": canonical_sha256(packet)}
                     for name, packet, kind in packets],
            "maximum_new_requests": 2 * len(packets), "max_tokens": 131072,
            "no_prompt_changes_during_trial": True, "scientific_independent_validation": False,
            "positive_candidates_are_not_independent_gold": True}
    immutable(out / "PLAN.json", plan)
    print("prepared", len(packets), "frozen review packets; no model calls", flush=True)
    return plan


async def run(out):
    plan = pilot.read(out / "PLAN.json")
    assert plan["source_sha256"] == source_tree_hash(ROOT)
    if (out / "SUMMARY.json").exists():
        return pilot.read(out / "SUMMARY.json")
    study = await pilot.study_for(out)
    study.audit_output_mode = plan.get("audit_output_mode")
    rows = []
    for task in plan["rows"]:
        if study.stop.exists():
            rows.append({**task, "status": "NOT_RUN_GLOBAL_STOP"})
            continue
        packet = pilot.read(out / "packets" / (task["case"] + ".json"))
        assert canonical_sha256(packet) == task["packet_sha256"]
        result = await audit_packet(study, packet, out / "reviews" / task["case"], max_tokens=plan["max_tokens"])
        verified = verify_registered_result(out / "reviews" / task["case"])
        reviews = result["reviews"]
        rows.append({**task, "status": result["status"],
                     "verdicts": [row.get("review", {}).get("verdict") for row in reviews],
                     "validation_errors": [row["validation_errors"] for row in reviews],
                     "raw_response_verification": verified,
                     "valid_two_rejections": len(reviews) == 2 and all(
                         row.get("review", {}).get("verdict") == "REJECT" and not row["validation_errors"]
                         for row in reviews)})
        atomic_json(out / "CHECKPOINT.json", {"rows": rows})
        print(task["case"], rows[-1]["status"], rows[-1]["verdicts"], rows[-1]["validation_errors"], flush=True)
    negative = [row for row in rows if row["private_kind"] != "UNMODIFIED_ENGINEERING_CANDIDATE"]
    positive = [row for row in rows if row["private_kind"] == "UNMODIFIED_ENGINEERING_CANDIDATE"]
    finished = [row for row in study.ledger_rows() if row["event"] == "REQUEST_FINISHED"]
    summary = {"planned": len(plan["rows"]), "rows": rows,
               "negative_valid_two_rejections": sum(row.get("valid_two_rejections", False) for row in negative),
               "negative_admissions_blocked": sum(row["status"] in {"QUARANTINED", "REJECTED"} for row in negative),
               "positive_valid_two_accepts": sum(row["status"] == "DEV_AUTO_AUDITED" for row in positive),
               "complete_responses": len(finished),
               "request_intents": sum(row["event"] == "REQUEST_INTENT" for row in study.ledger_rows()),
               "configured_cost_upper_usd_complete_only": sum(row["cost"]["upper_usd"] for row in finished),
               "stopped": study.stop.exists(), "invoice": "UNKNOWN", "formal_accepted": False,
               "scientific_independent_validation": False}
    atomic_json(out / "SUMMARY.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    prepare(out) if args.phase == "prepare" else asyncio.run(run(out))


if __name__ == "__main__":
    main()
