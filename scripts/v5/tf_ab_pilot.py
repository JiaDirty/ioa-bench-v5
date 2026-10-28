"""Frozen A/B pilot for the tree factory (M4 minimal online + M5 comparison).

Phases:
  preflight  authenticated catalog + one minimal JSON completion -> LIVE_MODEL_CONTRACT.json
  minimal    one real T331 treatment candidate end-to-end (the M4 online positive)
  prereg     freeze TASK_SET_FROZEN.json + AB_PREREGISTRATION.json
  ab         run both arms over the frozen tasks, audit protocol 1.2, admission, reports
  resume     zero-call terminal re-entry verification

Paid-request discipline: one attempt per unique request id, global stop on
401/403/unknown/budget (AihubmixStudy), USD soft 5 / hard 20 from the frozen config.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
SEALED_INDEX = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json"

from ioabench.config.loader import load_workspace_env
from ioabench.hashing import canonical_sha256
from ioabench.models.aihubmix import AIHubMixAdapter
from ioabench.v5.ai_generation import aihubmix_study
from ioabench.v5.ai_generation.auxiliary_runtime import classify_provider_failure
from ioabench.v5.ai_generation.development import admission, structure_vector, validate_policy
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V12, audit_pair
from ioabench.v5.ai_generation.factory import decode_json
from ioabench.v5.ai_generation.tree_factory import run_task
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.evaluation import atomic_json
from ioabench.runtime.full_manifest import source_tree_hash

POLICY_V12 = {"version": "ioabench.v5.development-policy/1.2.0",
              "scope": "DEVELOPMENT_AUTO_AUDITED", "provider": "aihubmix",
              "base_url": aihubmix_study.BASE_URL, "model_id": "deepseek-v4.1-flash-1017",
              "cross_family_exclusion": False, "human_gold_prerequisite": False,
              "formal_scientific_claims": False, "same_model_audit_independent_science": False,
              "formal_accepted": False, "minimum_recorded_strict_replays": 6,
              "near_duplicate_threshold": 0.9, "audit_efforts": ["high", "max"]}

T321_FULL_PROFILES = {"CONTROL": {"broker_alpha": "secure", "broker_beta": "secure", "broker_gamma": "secure"},
                      "RISK": {"broker_alpha": "basic", "broker_beta": "basic", "broker_gamma": "secure"}}
TASKS = [
    {"id": "T331-t1", "suite": "T331", "seed": 2024, "difficulty": "M", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation"}, "assertions": ["T331-A1"],
     "industry": "industry.medicine_supply"},
    {"id": "T331-t2", "suite": "T331", "seed": 2025, "difficulty": "M", "effort": "high",
     "target": {"confirmation_loop": "terminal_receipt_notes"}, "assertions": ["T331-A2"],
     "industry": "industry.payment_clearing"},
    {"id": "T331-t3", "suite": "T331", "seed": 2026, "difficulty": "H", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation", "confirmation_loop": "terminal_receipt_notes",
                "propagation_topology": "fork_join", "fanout_width": 3},
     "assertions": ["T331-A1", "T331-A2"], "industry": "industry.medicine_supply"},
    {"id": "T321-t1", "suite": "T321", "seed": 2024, "difficulty": "M", "effort": "high",
     "target": {"close_gate": "profile_verified"}, "assertions": ["T321-A1"],
     "industry": "industry.payment_clearing"},
    {"id": "T321-t2", "suite": "T321", "seed": 2025, "difficulty": "M", "effort": "high",
     "target": {"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": "broker_query",
                "close_gate": "profile_verified", "renegotiation_window": "after_final_delivery",
                "offer_profiles": T321_FULL_PROFILES},
     "assertions": ["T321-A1", "T321-A2"], "industry": "industry.medicine_supply"},
    {"id": "T321-t3", "suite": "T321", "seed": 2026, "difficulty": "H", "effort": "high",
     "target": {"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": "broker_query",
                "renegotiation_window": "after_final_delivery", "offer_profiles": T321_FULL_PROFILES},
     "assertions": ["T321-A2"], "industry": "industry.payment_clearing"},
    {"id": "T362-t1", "suite": "T362", "seed": 2024, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "source_release": "per_owner_turn"},
     "assertions": ["T362-A1"], "industry": "industry.medicine_supply"},
    {"id": "T362-t2", "suite": "T362", "seed": 2025, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "relay_before_digest": "required"},
     "assertions": ["T362-A2"], "industry": "industry.payment_clearing"},
    {"id": "T362-t3", "suite": "T362", "seed": 2026, "difficulty": "H", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "source_release": "per_owner_turn",
                "relay_before_digest": "required"},
     "assertions": ["T362-A1", "T362-A2"], "industry": "industry.medicine_supply"},
]
ROUTES = ("treatment_tree_ir", "baseline_4stage")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


async def study_for(out: Path):
    load_workspace_env(ROOT / ".env")
    import os
    if not os.environ.get("AIHUBMIX_API_KEY"):
        raise ValueError("AIHUBMIX_API_KEY missing; no value logged")
    port = AIHubMixAdapter(stop_on_provider_error=True, request_timeout=900)
    catalog_path = out / "MODEL_CATALOG.json"
    catalog = read(catalog_path) if catalog_path.exists() else \
        list(await port.discover_models())
    atomic_json(catalog_path, catalog)
    return aihubmix_study.AihubmixStudy(out, port, catalog)


def load_index():
    index = read(SEALED_INDEX)
    return index


def extend_index(index, directory: Path):
    from copy import deepcopy
    from ioabench.v5.ai_generation.history import build_index
    merged = deepcopy(index)
    # build_index consumes case FILES (PAIR.json), not directories
    addition = build_index(ROOT, sources=[directory / "PAIR.json"])
    records = {row["case_sha256"]: row for row in merged["records"]}
    for row in addition["records"]:
        prior = records.get(row["case_sha256"])
        if prior:
            prior["occurrences"].extend(item for item in row["occurrences"]
                                        if item not in prior["occurrences"])
        else:
            records[row["case_sha256"]] = row
    merged["records"] = list(records.values())
    return merged


async def phase_preflight(out: Path):
    study = await study_for(out)
    from dataclasses import asdict
    entry = study.catalog_entry
    probe = await study.invoke(out / "probes", "json-receipt-v2",
                               [{"role": "user", "content":
                                 'Return only JSON exactly like {"receipt":"tf-20261024-r1","ok":true} with those exact values.'}],
                               aihubmix_study.parameters("high", max_tokens=2048))
    payload = decode_json(probe.text)
    transport = probe.provider_metadata.get("transport_metadata") or {}
    contract = {"version": "ioabench.v5.live-model-contract/1.0.0",
                "checked_at_utc": utc(), "provider": aihubmix_study.PROVIDER,
                "base_url": aihubmix_study.BASE_URL, "model_id": aihubmix_study.MODEL,
                "endpoint_family": "openai.chat_completions",
                "catalog_entry": {key: entry.get(key) for key in
                                  ("id", "model_id", "developer_id", "owned_by", "features")},
                "served_body_model": probe.provider_metadata.get("model"),
                "gateway_header_model": transport.get("x-aihubmix-model"),
                "served_matches_request": (transport.get("x-aihubmix-model") == aihubmix_study.MODEL
                                           or probe.provider_metadata.get("model") == aihubmix_study.MODEL),
                "http_status": transport.get("http_status"),
                "finish_reason": probe.finish_reason,
                "usage_reported": dict(probe.usage),
                "json_object_returned": isinstance(payload, dict),
                "receipt_value_exact": payload.get("receipt") == "tf-20261024-r1",
                "receipt_value_note": "content fidelity is per-call evidence; the pipeline's "
                                      "decode/schema gates judge it per request",
                "api_key_present": True,
                "key_value_or_header_logged": False,
                "budget": {"soft_usd": aihubmix_study.SOFT_SPEND_USD,
                           "hard_usd": aihubmix_study.HARD_SPEND_USD},
                "schema": await study.port.describe_model(aihubmix_study.MODEL)}
    atomic_json(out / "LIVE_MODEL_CONTRACT.json", contract)
    print(json.dumps({"served": contract["served_body_model"],
                      "gateway_header": contract["gateway_header_model"],
                      "http": contract["http_status"],
                      "json_ok": contract["json_object_returned"],
                      "receipt_exact": contract["receipt_value_exact"],
                      "usage": contract["usage_reported"], "finish": contract["finish_reason"]}))
    if not contract["served_matches_request"] or not contract["json_object_returned"] \
            or probe.finish_reason != "stop" or transport.get("http_status") != 200:
        raise ValueError("preflight contract failed; stop before paid generation")


async def audit_one(study, source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    # streaming transport removed the gateway's non-streaming time cutoff, so the
    # full 65536 budget is safe again and lets thinking complete before prose
    review = await audit_pair(study, source, destination / "audit", protocol=PROTOCOL_V12,
                              max_tokens=65536)
    pair = read(source / "PAIR.json")
    control = next(case_from_dict(case, allow_dynamic=True) for case in pair if case["arm"] == "CONTROL")
    record = admission(source, review, structure_vector(control),
                       audit_directory=destination / "audit")
    atomic_json(destination / "ADMISSION.json", record)
    return record


async def phase_minimal(out: Path):
    study = await study_for(out)
    if study.stop.exists():
        raise ValueError("study stopped; no new paid requests")
    index = load_index()
    references = [row["features"] for row in index["records"]]
    task = dict(TASKS[0], id="T331-minimal-online")
    result = await run_task(study, task, index, references, workspace=ROOT,
                            policy=validate_policy(dict(POLICY_V12)),
                            out=out / "minimal", route="treatment_tree_ir")
    summary = {"task": task["id"], "route": result["route"], "status": result["status"],
               "failed_stage": result.get("failed_stage"), "state": result.get("state")}
    if result["status"] == "PASS":
        record = await audit_one(study, out / "minimal/candidates" / task["id"],
                                 out / "minimal/reviews" / task["id"])
        summary["audit_status"] = record["audit_status"]
        summary["admission"] = record["status"]
    atomic_json(out / "T331_MINIMAL_ONLINE.json", {**summary, "provider_calls": None,
                                                    "evidence": str(out / "minimal")})
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def phase_prereg(out: Path):
    frozen = {"version": "ioabench.v5.ab-task-set/1.0.0", "frozen_at_utc": utc(),
              "tasks": TASKS, "routes": list(ROUTES),
              "unit": "(suite, target_mechanism_cell, route, seed, difficulty_intent)",
              "history_base": {"path": SEALED_INDEX.relative_to(ROOT).as_posix(),
                               "sha256": __import__("hashlib").sha256(
                                   SEALED_INDEX.read_bytes()).hexdigest(),
                               "records": len(load_index()["records"])},
              "model": {"provider": aihubmix_study.PROVIDER, "model_id": aihubmix_study.MODEL,
                        "effort": "high"},
              "audit": {"protocol": PROTOCOL_V12, "efforts": ["high", "max"], "max_tokens": 65536},
              "dedup_threshold": 0.9, "history_scope": "FULL_HISTORY",
              "runtime_sha256": source_tree_hash(ROOT)}
    atomic_json(out / "TASK_SET_FROZEN.json", frozen)
    prereg = {"version": "ioabench.v5.ab-preregistration/1.0.0",
              "frozen_at_utc": utc(), "task_set_sha256": canonical_sha256(frozen),
              "baseline": "existing four-stage staged_proposal G2 (task_design/world_graph/risk_placement/surface_artifacts)",
              "treatment": "scenario-tree business package + typed MechanismIR skeleton + static capability lattice check + one bounded payload proposal call + format-fix repair <=1",
              "same_gates": ["compile_and_gate pair gate", "reference execution matrix",
                             "oracle firewall", "execution fidelity + design-assertion witnesses",
                             "all-history dedup (0.9)", "strict replay >=6", "protocol-1.2 two-effort audit",
                             "development admission"],
              "cross_arm_dedup": "each arm extends the same in-run index; cross-route collisions recorded separately",
              "metrics": ["first_attempt_rate", "final_rate_after_bounded_repair",
                          "new_accepted_pairs", "cost_bounds", "failure_funnel"],
              "not_run_after_stop": "counts stay in the preregistered denominator",
              "formal_accepted": False}
    atomic_json(out / "AB_PREREGISTRATION.json", prereg)
    print(json.dumps({"frozen_tasks": len(TASKS), "routes": list(ROUTES)}))


async def phase_ab(out: Path, *, limit: int | None = None, route_first: str = "treatment_tree_ir"):
    frozen = read(out / "TASK_SET_FROZEN.json")
    study = await study_for(out)
    index = load_index()
    references = [row["features"] for row in index["records"]]
    policy = validate_policy(dict(POLICY_V12))
    routes = ("treatment_tree_ir", "baseline_4stage")
    if route_first == "baseline_4stage":
        routes = ("baseline_4stage", "treatment_tree_ir")
    rows, started, accepted = [], 0, 0
    for route in routes:
        for task in frozen["tasks"]:
            candidate_id = task["id"] + "-" + ("T" if route == "treatment_tree_ir" else "B")
            directory = out / "ab/candidates" / candidate_id
            if study.stop.exists():
                rows.append({"task": task["id"], "route": route, "status": "NOT_RUN_GLOBAL_STOP"})
                continue
            if (directory / "RESULT.json").exists():
                result = read(directory / "RESULT.json")
            else:
                if limit is not None and started >= limit:
                    rows.append({"task": task["id"], "route": route, "status": "NOT_RUN_LIMIT"})
                    continue
                extended = dict(task, id=candidate_id)
                result = await run_task(study, extended, index, references, workspace=ROOT,
                                        policy=policy, out=out / "ab", route=route)
                started += 1
            record = None
            if result.get("status") == "PASS" and not study.stop.exists():
                try:
                    record = await audit_one(study, directory, out / "ab/reviews" / candidate_id)
                except Exception as exc:
                    # an unresolved audit terminal seals THIS candidate; the batch
                    # continues with the next NEW request ids (frozen protocol)
                    category = classify_provider_failure(exc)
                    record = {"audit_status": "AUDIT_REQUEST_FAILED",
                              "status": "QUARANTINED",
                              "hard_gate_errors": [f"{type(exc).__name__}:{category}"],
                              "recorded_strict_replays": 0, "history_scope": "FULL_HISTORY"}
                    if category not in {"REQUEST_UNRESOLVED", "UNKNOWN", "AUTH/PERMISSION",
                                        "INSUFFICIENT_BALANCE", "MISSING_SECRET"}:
                        record["hard_gate_errors"] = [f"{type(exc).__name__}:local"]
                if record.get("status") == "DEV_ACCEPTED":
                    index = extend_index(index, directory)
                    references = [row["features"] for row in index["records"]]
                    accepted += 1
            rows.append({"task": task["id"], "route": route, "status": result["status"],
                         "failed_stage": result.get("failed_stage"),
                         "audit_status": record["audit_status"] if record else None,
                         "admission": record["status"] if record else None,
                         "history_statuses": result.get("history_statuses")})
            print(candidate_id, result["status"], result.get("failed_stage", ""),
                  record["status"] if record else "", flush=True)
            if study.stop.exists():
                break
        if study.stop.exists():
            break
    write_reports(out, rows, frozen)
    return rows


def write_reports(out: Path, rows, frozen):
    ab_dir = out / "ab"
    with (ab_dir / "AB_RESULTS.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["task", "route", "status", "failed_stage",
                                                    "audit_status", "admission", "history_statuses"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "history_statuses": ";".join(row.get("history_statuses") or [])})
    ledger_path = out / "REQUEST_LEDGER.jsonl"
    finished = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()] \
        if ledger_path.exists() else []
    paid = [row for row in finished if row.get("event") == "REQUEST_FINISHED"]
    upper_usd = sum((row.get("cost") or {}).get("upper_usd") or row.get("budget_reserve_usd") or 0
                    for row in paid)
    accepted = [row for row in rows if row.get("admission") == "DEV_ACCEPTED"]
    cost = {"version": "ioabench.v5.cost-and-yield/1.0.0", "currency": "USD",
            "paid_completions": len(paid), "upper_usd_bound": round(upper_usd, 6),
            "actual_invoice": "UNKNOWN",
            "new_accepted_pairs": len(accepted),
            "unit_cost_upper_usd_per_new_accepted_pair":
                round(upper_usd / len(accepted), 6) if accepted else "NOT_COMPUTABLE",
            "sunk_prior_rounds_excluded": True}
    atomic_json(ab_dir / "COST_AND_YIELD.json", cost)
    with (ab_dir / "FAILURE_FUNNEL.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["stage", "count"])
        for stage, count in sorted(Counter(
                row.get("failed_stage") or row["status"] for row in rows).items()):
            writer.writerow([stage, count])
    atomic_json(ab_dir / "RUN_SUMMARY.json", {"rows": rows, "counter": dict(Counter(
        row["status"] for row in rows)), "frozen_tasks": len(frozen["tasks"])})


def phase_resume(out: Path):
    """Terminal re-entry: verify sealed results without any provider call."""
    import hashlib
    before = hashlib.sha256((out / "REQUEST_LEDGER.jsonl").read_bytes()).hexdigest() \
        if (out / "REQUEST_LEDGER.jsonl").exists() else None
    count = 0
    for result_path in sorted((out / "ab/candidates").glob("*/RESULT.json")):
        row = read(result_path)
        if row.get("status") not in {"PASS", "REJECTED", "PIPELINE_FAILED", "BLOCKED_EXTERNAL"}:
            raise ValueError("non-terminal result in sealed evidence")
        count += 1
    after = hashlib.sha256((out / "REQUEST_LEDGER.jsonl").read_bytes()).hexdigest() \
        if (out / "REQUEST_LEDGER.jsonl").exists() else None
    value = {"status": "PASS", "sealed_results": count,
             "ledger_unchanged": before == after, "provider_calls": 0}
    atomic_json(out / "AB_RESUME.json", value)
    print(json.dumps(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True,
                        choices=("preflight", "minimal", "prereg", "ab", "resume"))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    out = OUT
    if args.phase == "preflight":
        asyncio.run(phase_preflight(out))
    elif args.phase == "minimal":
        asyncio.run(phase_minimal(out))
    elif args.phase == "prereg":
        phase_prereg(out)
    elif args.phase == "ab":
        asyncio.run(phase_ab(out, limit=args.limit))
    else:
        phase_resume(out)


if __name__ == "__main__":
    raise SystemExit(main())
