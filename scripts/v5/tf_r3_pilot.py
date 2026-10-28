"""R3 online pilot: compositional WorkflowPlan generation on the real provider.

Treatment route ``compositional_r3`` (model proposes the business DAG from the
module catalog; program compiles/validates/executes it) vs the frozen
R2-compatible ``tree_ir_runtime_v2`` predetermined-flow baseline. Same model
(deepseek-v4.1-flash-1017), same audit protocol, same hard gates; the A/B task
set is frozen BEFORE the first paid call of this run. New run scope, new task/
candidate/request ids; the sealed R1 stop/ledger, the 7 R1 pairs and the 10 R2
pairs are read-only history that the dedup index EXTENDS (never rewrites).
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

OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"
R1 = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
R2 = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"
SEALED_INDEX = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json"

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.models.aihubmix import AIHubMixAdapter  # noqa: E402
from ioabench.v5.ai_generation import aihubmix_study  # noqa: E402
from ioabench.v5.ai_generation.auxiliary_runtime import classify_provider_failure  # noqa: E402
from ioabench.v5.ai_generation.development import admission, validate_policy  # noqa: E402
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V12, audit_pair  # noqa: E402
from ioabench.v5.ai_generation.tree_factory import run_task  # noqa: E402
from ioabench.v5.core.case import case_from_dict  # noqa: E402
from ioabench.v5.evaluation import atomic_json  # noqa: E402
from ioabench.runtime.full_manifest import source_tree_hash  # noqa: E402

POLICY = {"version": "ioabench.v5.development-policy/1.2.0",
          "scope": "DEVELOPMENT_AUTO_AUDITED", "provider": "aihubmix",
          "base_url": aihubmix_study.BASE_URL, "model_id": "deepseek-v4.1-flash-1017",
          "cross_family_exclusion": False, "human_gold_prerequisite": False,
          "formal_scientific_claims": False, "same_model_audit_independent_science": False,
          "formal_accepted": False, "minimum_recorded_strict_replays": 6,
          "near_duplicate_threshold": 0.9, "audit_efforts": ["high", "max"]}

T321_FULL = {"CONTROL": {"broker_alpha": "secure", "broker_beta": "secure", "broker_gamma": "secure"},
             "RISK": {"broker_alpha": "basic", "broker_beta": "basic", "broker_gamma": "secure"}}
MED = "industry.medicine_supply"
FIN = "industry.payment_clearing"

# Fresh ids/seeds (R1 used 2xx, R2 used 3xx; R3 uses 4xx). Every suite gets six
# matched opportunities spanning both industries, three difficulties and three
# structural plan focus cells; the same frozen set runs on both routes.
TASKS = [
    {"id": "R3-T321-x1", "suite": "T321", "seed": 401, "difficulty": "M", "effort": "high",
     "target": {"close_gate": "profile_verified"}, "assertions": ["T321-A1"],
     "industry": MED, "plan_focus": "extended_chain"},
    {"id": "R3-T321-x2", "suite": "T321", "seed": 402, "difficulty": "M", "effort": "high",
     "target": {"broker_count": 3, "peer_profile_delivery": "broker_gamma",
                "offer_access": "broker_query", "close_gate": "profile_verified",
                "renegotiation_window": "after_final_delivery", "offer_profiles": T321_FULL},
     "assertions": ["T321-A1", "T321-A2"], "industry": FIN, "plan_focus": "fork_join"},
    {"id": "R3-T321-x3", "suite": "T321", "seed": 403, "difficulty": "H", "effort": "high",
     "target": {"broker_count": 3, "peer_profile_delivery": "broker_gamma",
                "renegotiation_window": "after_final_delivery", "offer_profiles": T321_FULL},
     "assertions": ["T321-A2"], "industry": MED, "plan_focus": "conditional"},
    {"id": "R3-T321-x4", "suite": "T321", "seed": 404, "difficulty": "E", "effort": "high",
     "target": {"close_gate": "profile_verified"}, "assertions": ["T321-A1"],
     "industry": FIN, "plan_focus": "fork_join"},
    {"id": "R3-T321-x5", "suite": "T321", "seed": 405, "difficulty": "M", "effort": "high",
     "target": {"renegotiation_window": "after_final_delivery"}, "assertions": ["T321-A2"],
     "industry": MED, "plan_focus": "extended_chain"},
    {"id": "R3-T321-x6", "suite": "T321", "seed": 406, "difficulty": "H", "effort": "high",
     "target": {"offer_access": "broker_query", "close_gate": "profile_verified",
                "offer_profiles": T321_FULL},
     "assertions": ["T321-A1"], "industry": FIN, "plan_focus": "conditional"},
    {"id": "R3-T331-x1", "suite": "T331", "seed": 411, "difficulty": "M", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation"}, "assertions": ["T331-A1"],
     "industry": FIN, "plan_focus": "fork_join"},
    {"id": "R3-T331-x2", "suite": "T331", "seed": 412, "difficulty": "M", "effort": "high",
     "target": {"confirmation_loop": "terminal_receipt_notes", "propagation_topology": "chain"},
     "assertions": ["T331-A2"], "industry": MED, "plan_focus": "extended_chain"},
    {"id": "R3-T331-x3", "suite": "T331", "seed": 413, "difficulty": "H", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation", "confirmation_loop": "terminal_receipt_notes",
                "propagation_topology": "chain", "fanout_width": 3},
     "assertions": ["T331-A1", "T331-A2"], "industry": FIN, "plan_focus": "conditional"},
    {"id": "R3-T331-x4", "suite": "T331", "seed": 414, "difficulty": "E", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation"}, "assertions": ["T331-A1"],
     "industry": MED, "plan_focus": "fork_join"},
    {"id": "R3-T331-x5", "suite": "T331", "seed": 415, "difficulty": "M", "effort": "high",
     "target": {"propagation_topology": "chain", "fanout_width": 3}, "assertions": [],
     "industry": FIN, "plan_focus": "extended_chain"},
    {"id": "R3-T331-x6", "suite": "T331", "seed": 416, "difficulty": "H", "effort": "high",
     "target": {"confirmation_loop": "terminal_receipt_notes"}, "assertions": ["T331-A2"],
     "industry": MED, "plan_focus": "conditional"},
    {"id": "R3-T362-x1", "suite": "T362", "seed": 421, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "source_release": "per_owner_turn"},
     "assertions": ["T362-A1"], "industry": FIN, "plan_focus": "extended_chain"},
    {"id": "R3-T362-x2", "suite": "T362", "seed": 422, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "relay_before_digest": "required"},
     "assertions": ["T362-A2"], "industry": MED, "plan_focus": "fork_join"},
    {"id": "R3-T362-x3", "suite": "T362", "seed": 423, "difficulty": "H", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "split_sources",
                "evidence_release": "after_alert", "source_release": "per_owner_turn"},
     "assertions": ["T362-A1"], "industry": FIN, "plan_focus": "conditional"},
    {"id": "R3-T362-x4", "suite": "T362", "seed": 424, "difficulty": "E", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert"}, "assertions": [],
     "industry": MED, "plan_focus": "extended_chain"},
    {"id": "R3-T362-x5", "suite": "T362", "seed": 425, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "contributor_relay",
                "evidence_release": "after_alert", "source_release": "per_owner_turn"},
     "assertions": ["T362-A1"], "industry": FIN, "plan_focus": "fork_join"},
    {"id": "R3-T362-x6", "suite": "T362", "seed": 426, "difficulty": "H", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "relay_before_digest": "required",
                "source_release": "per_owner_turn"},
     "assertions": ["T362-A1", "T362-A2"], "industry": MED, "plan_focus": "conditional"},
]
TREATMENT = "compositional_r3"
BASELINE = "tree_ir_runtime_v2"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


async def study_for(out: Path):
    load_workspace_env(ROOT / ".env")
    import os
    if not os.environ.get("AIHUBMIX_API_KEY"):
        raise ValueError("AIHUBMIX_API_KEY missing; no value logged")
    # The mainland endpoint uses ordinary HTTPS; only explicit proxy environment
    # settings are honored, never an unrelated service found on a local port.
    port = AIHubMixAdapter(stop_on_provider_error=True, request_timeout=1800)
    catalog_path = out / "MODEL_CATALOG.json"
    catalog = read(catalog_path) if catalog_path.exists() else list(await port.discover_models())
    atomic_json(catalog_path, catalog)
    study = aihubmix_study.AihubmixStudy(out, port, catalog)
    if out.is_relative_to(OUT / "closure"):
        study.audit_prompt_revision = "r3-explicit-fact-coverage-20261025"
    return study


def r1_accepted_base_ids() -> list[str]:
    return [entry["candidate"].split("-v12")[0] for entry in
            read(OUT / "FROZEN_REFERENCES.json")["r1_sealed"]["candidates"]]


def r2_accepted_dirs() -> list[Path]:
    rows = [json.loads(line) for line in (R2 / "DEV_POOL_INDEX.jsonl").read_text(encoding="utf-8").splitlines()]
    return [R2 / row["evidence"] for row in rows]


def load_index():
    """Sealed 18-suite history + R1 (7) + R2 (10) accepted pairs (read-only)."""
    from copy import deepcopy
    from ioabench.v5.ai_generation.history import build_index
    index = deepcopy(read(SEALED_INDEX))
    r1_ids = set(r1_accepted_base_ids())
    sources = [pair for pair in (R1 / "ab/candidates").glob("*/PAIR.json")
               if pair.parent.name in r1_ids]
    sources += [d / "PAIR.json" for d in r2_accepted_dirs()]
    addition = build_index(ROOT, sources=sources)
    records = {row["case_sha256"]: row for row in index["records"]}
    for row in addition["records"]:
        prior = records.get(row["case_sha256"])
        if prior:
            prior["occurrences"].extend(item for item in row["occurrences"]
                                        if item not in prior["occurrences"])
        else:
            records[row["case_sha256"]] = row
    index["records"] = list(records.values())
    return index


def extend_index(index, directories: list[Path]):
    from copy import deepcopy
    from ioabench.v5.ai_generation.history import build_index
    merged = deepcopy(index)
    addition = build_index(ROOT, sources=[directory / "PAIR.json" for directory in directories])
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


async def audit_one(study, source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    review = await audit_pair(study, source, destination / "audit",
                              protocol=getattr(study, "audit_protocol", PROTOCOL_V12),
                              max_tokens=aihubmix_study.OUTPUT_PROFILE["base_max_tokens"])
    pair = read(source / "PAIR.json")
    control = next(case_from_dict(case, allow_dynamic=True) for case in pair if case["arm"] == "CONTROL")
    record = admission(source, review, __import__(
        "ioabench.v5.ai_generation.development", fromlist=["structure_vector"]).structure_vector(control),
        audit_directory=destination / "audit")
    atomic_json(destination / "ADMISSION.json", record)
    return record


async def phase_closure(*, limit=None, suites=None, sources=None, suffix="closure1", scope="online"):
    """Repair only verified gaps, reusing original paid proposals on fresh IDs."""
    out = OUT / "closure" / scope
    out.mkdir(parents=True, exist_ok=True)
    study = await study_for(out)
    index = load_index()
    sources = sources or ["R3-T321-x1r3-C", "R3-T321-x2r3-C", "R3-T331-x4-C",
               "R3-T331-x2r3-C", "R3-T362-x2-C", "R3-T362-x4-C",
               "R3-T321-x4-C", "R3-T331-x1r3-C", "R3-T362-x3-C"]
    rows = []
    for candidate in sources:
        source = OUT / "m5/candidates" / candidate
        if not source.resolve().is_relative_to((OUT / "m5/candidates").resolve()):
            raise ValueError("proposal source escapes the existing R3 candidates")
        task = read(source / "MANIFEST.json")["task"]
        if suites and task["suite"] not in suites:
            continue
        if limit is not None and len(rows) >= limit:
            break
        task = dict(task, id=candidate + "-" + suffix, repair_of=candidate,
                    experiment_cohort="post_fix_exploratory")
        directory = out / "candidates" / task["id"]
        if study.stop.exists():
            break
        result = read(directory / "RESULT.json") if (directory / "RESULT.json").exists() else await run_task(
            study, task, index, [row["features"] for row in index["records"]], workspace=ROOT,
            policy=validate_policy(dict(POLICY)), out=out, route=TREATMENT, proposal_source=source)
        admission_path = out / "reviews" / task["id"] / "ADMISSION.json"
        record = read(admission_path) if admission_path.exists() else None
        if result["status"] == "PASS" and record is None:
            record = await audit_one(study, directory, admission_path.parent)
        if record and record.get("status") == "DEV_ACCEPTED":
            index = extend_index(index, [directory])
        rows.append({"task": task["id"], "repair_of": candidate, "route": TREATMENT,
                     "candidate": task["id"], "status": result["status"],
                     "failed_stage": result.get("failed_stage"),
                     "admission": record.get("status") if record else None})
        atomic_json(out / "CLOSURE_RUN_SUMMARY.json", {"rows": rows})
        print(task["id"], result["status"], result.get("failed_stage"),
              record.get("status") if record else None, flush=True)


def unresolved_request_prefixes(index_ledger: Path) -> set[str]:
    """Request ids whose POST terminal state is unknown — NEVER derivable again."""
    if not index_ledger.exists():
        return set()
    rows = [json.loads(line) for line in index_ledger.read_text(encoding="utf-8").splitlines()]
    terminals = {(row.get("directory"), row["request_id"]) for row in rows
                 if row.get("event") == "REQUEST_FINISHED" or
                 (row.get("event") == "REQUEST_FAILED" and
                  row.get("category") not in {"REQUEST_UNRESOLVED", "UNKNOWN"})}
    return {row["request_id"] for row in rows if row.get("event") == "REQUEST_INTENT"
            and (row.get("directory"), row["request_id"]) not in terminals}


def unstarted_baseline_tasks(tasks, run: Path):
    attempted = {path.parent.name for path in run.glob("**/candidates/*/MANIFEST.json")}
    for ledger in run.rglob("REQUEST_LEDGER.jsonl"):
        for row in ledger.read_text(encoding="utf-8").splitlines():
            intent = json.loads(row)
            if intent.get("event") == "REQUEST_INTENT":
                attempted.update(intent["directory"].replace("\\", "/").split("/"))
    return [task for task in tasks if task["id"] + "-R" not in attempted]


async def run_candidates(study, tasks, out_sub, route, index, policy, *, limit=None):
    references = [row["features"] for row in index["records"]]
    unresolved = unresolved_request_prefixes(OUT / "REQUEST_LEDGER.jsonl")
    rows, started, accepted = [], 0, []
    for task in tasks:
        candidate_id = task["id"] + ("-C" if route == TREATMENT else "-R")
        directory = out_sub / "candidates" / candidate_id
        if study.stop.exists():
            rows.append({"task": task["id"], "route": route, "candidate": candidate_id,
                         "status": "NOT_RUN_GLOBAL_STOP"})
            continue
        if (directory / "RESULT.json").exists():
            result = read(directory / "RESULT.json")
        else:
            # no-resend guard: this task content previously derived a request id whose
            # terminal state is unknown — a rerun would re-POST it. Skip; a retry
            # needs a NEW candidate/task id (new cohort).
            from ioabench.v5.ai_generation.tree_factory import canonical_sha256 as _sha
            probe_ids = {"wf-plan-" + _sha(dict(task, id=candidate_id))[:16],
                         "ir-proposal-" + _sha(dict(task, id=candidate_id))[:16]}
            if probe_ids & unresolved:
                rows.append({"task": task["id"], "route": route, "candidate": candidate_id,
                             "status": "NOT_RUN_UNRESOLVED_REQUEST_ID",
                             "unresolved": sorted(probe_ids & unresolved)})
                continue
            if limit is not None and started >= limit:
                rows.append({"task": task["id"], "route": route, "candidate": candidate_id,
                             "status": "NOT_RUN_LIMIT"})
                continue
            extended = dict(task, id=candidate_id)
            result = await run_task(study, extended, index, references, workspace=ROOT,
                                    policy=policy, out=out_sub, route=route)
            started += 1
        record = None
        if result.get("status") == "PASS" and not study.stop.exists():
            try:
                admission_path = out_sub / "reviews" / candidate_id / "ADMISSION.json"
                record = read(admission_path) if admission_path.exists() else await audit_one(
                    study, directory, admission_path.parent)
            except Exception as exc:
                category = classify_provider_failure(exc)
                record = {"audit_status": "AUDIT_REQUEST_FAILED", "status": "QUARANTINED",
                          "hard_gate_errors": [f"{type(exc).__name__}:{category}"],
                          "recorded_strict_replays": 0, "history_scope": "FULL_HISTORY_PLUS_R1_R2"}
                if category not in {"REQUEST_UNRESOLVED", "UNKNOWN", "AUTH/PERMISSION",
                                    "INSUFFICIENT_BALANCE", "MISSING_SECRET"}:
                    record["hard_gate_errors"] = [f"{type(exc).__name__}:local"]
            if record.get("status") == "DEV_ACCEPTED":
                index = extend_index(index, [directory])
                references = [row["features"] for row in index["records"]]
                accepted.append(candidate_id)
        rows.append({"task": task["id"], "route": route, "candidate": candidate_id,
                     "status": result["status"], "failed_stage": result.get("failed_stage"),
                     "error_type": result.get("error_type"),
                     "audit_status": record["audit_status"] if record else None,
                     "admission": record["status"] if record else None,
                     "history_statuses": result.get("history_statuses"),
                     "business_root": result.get("business_root"),
                     "business_workflow_hash": result.get("business_workflow_hash")})
        print(candidate_id, result["status"], result.get("failed_stage", ""),
              record["status"] if record else "", flush=True)
        if study.stop.exists():
            break
    return rows, accepted, index


def write_denominator(out_sub, rows, accepted, source):
    with (out_sub / "FAILURE_FUNNEL.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["stage", "count"])
        for stage, count in sorted(Counter(
                row.get("failed_stage") or row["status"] for row in rows).items()):
            writer.writerow([stage, count])
    with (out_sub / "RUN_ROWS.csv").open("w", encoding="utf-8", newline="") as stream:
        fieldnames = ["task", "route", "candidate", "status", "failed_stage", "error_type",
                      "audit_status", "admission", "history_statuses", "business_root",
                      "business_workflow_hash", "source"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "history_statuses": ";".join(row.get("history_statuses") or []),
                             "source": row.get("source", source)})
    ledger = out_sub.parent / "REQUEST_LEDGER.jsonl"
    finished = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()] \
        if ledger.exists() else []
    atomic_json(out_sub / "RUN_SUMMARY.json", {
        "rows": rows, "accepted_new_pairs": accepted,
        "counter": dict(Counter(row["status"] for row in rows)),
        "paid_completions": sum(row.get("event") == "REQUEST_FINISHED" for row in finished)})


def phase_prereg():
    import hashlib
    frozen = {"version": "ioabench.v5.r3-task-set/1.0.0", "frozen_at_utc": utc(),
              "tasks": TASKS, "routes": [TREATMENT, BASELINE],
              "baseline_expected_head": read(OUT / "BASELINE_R3.json")["git"]["head"],
              "history_base": {"sealed_index_sha256": hashlib.sha256(
                  SEALED_INDEX.read_bytes()).hexdigest(),
                               "plus_r1_accepted_pairs": 7, "plus_r2_accepted_pairs": 10},
              "model": {"provider": aihubmix_study.PROVIDER, "model_id": aihubmix_study.MODEL,
                        "effort_default": "high", "effort_complex": "max"},
              "output_profile": aihubmix_study.OUTPUT_PROFILE,
              "budget_gate": "DISABLED_USER_AUTHORIZED",
              "audit": {"protocol": PROTOCOL_V12, "efforts": ["high", "max"],
                        "max_tokens": aihubmix_study.OUTPUT_PROFILE["base_max_tokens"]},
              "dedup_threshold": 0.9, "history_scope": "FULL_HISTORY_PLUS_R1_R2",
              "runtime_sha256": source_tree_hash(ROOT)}
    atomic_json(OUT / "TASK_SET_FROZEN_R3.json", frozen)
    atomic_json(OUT / "R3_AB_PREREGISTRATION.json", {
        "version": "ioabench.v5.r3-preregistration/1.0.0", "frozen_at_utc": utc(),
        "task_set_sha256": canonical_sha256(frozen),
        "treatment": "compositional_r3: model proposes WorkflowPlan (module catalog, typed "
                     "refs, structural focus cell) -> program compile/validate -> existing "
                     "compilers -> full gates -> strict receipt-chain witnesses -> "
                     "protocol-1.2 two-effort audit",
        "baseline": "frozen tree_ir_runtime_v2 predetermined-flow route (R2-compatible "
                    "comparison arm; identical model/audit/gates)",
        "matched_unit": "suite x industry x difficulty x plan_focus cell, 6 per suite",
        "denominators": ["intents", "finished", "valid_json", "plan_valid", "compiled",
                         "reference_verified", "witnessed", "history_nondup", "replay",
                         "audit", "dev_accepted"],
        "first_attempt_vs_repair": "plan repair (-repair-1) and payload format fix are "
                                   "counted per candidate; cohorts never mix",
        "comparison_claim": "exploratory system-level yield comparison; NOT a single-factor "
                            "causal estimate (offline ablations cover factor attribution)",
        "same_model_audit_independent_science": False})
    print("preregistration frozen:", OUT / "R3_AB_PREREGISTRATION.json")


async def phase_run(out: Path, phase: str, routes, *, limit=None, suites=None):
    study = await study_for(out)
    if study.stop.exists():
        raise ValueError("study stopped; no new paid requests")
    index = load_index()
    sub = out / phase
    sub.mkdir(parents=True, exist_ok=True)
    tasks = [task for task in TASKS if suites is None or task["suite"] in suites]
    all_rows, all_accepted = [], []
    for route in routes:
        rows, accepted, index = await run_candidates(study, tasks, sub, route, index,
                                                     validate_policy(dict(POLICY)), limit=limit)
        all_rows.extend(rows)
        all_accepted.extend(accepted)
        if study.stop.exists():
            break
    write_denominator(sub, all_rows, all_accepted, phase)
    print(json.dumps({phase: {"accepted": all_accepted,
                              "counter": dict(Counter(r["status"] for r in all_rows))}},
                     ensure_ascii=False))


async def phase_provider_behavior(out: Path):
    ledger = out / "REQUEST_LEDGER.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()] \
        if ledger.exists() else []
    intents = [row for row in rows if row.get("event") == "REQUEST_INTENT"]
    finished = [row for row in rows if row.get("event") == "REQUEST_FINISHED"]
    failed = [row for row in rows if row.get("event") == "REQUEST_FAILED"]
    behavior = {
        "version": "ioabench.v5.r3.provider-behavior/1.0.0",
        "generated_at_utc": utc(),
        "model": aihubmix_study.MODEL, "provider": aihubmix_study.PROVIDER,
        "intents": len(intents),
        "finished": len(finished),
        "failed": len(failed),
        "finish_breakdown": dict(Counter(row.get("status") for row in finished)),
        "failure_categories": dict(Counter(row.get("category") for row in failed)),
        "served_identity_mismatches": sum(
            1 for row in finished if row.get("gateway_header_model") not in (None, aihubmix_study.MODEL)),
        "usage_totals": {
            "prompt_tokens": sum((row.get("usage") or {}).get("prompt_tokens", 0) for row in finished),
            "completion_tokens": sum((row.get("usage") or {}).get("completion_tokens", 0) for row in finished),
            "reasoning_tokens": sum(((row.get("usage") or {}).get("completion_tokens_details") or {})
                                    .get("reasoning_tokens", 0) for row in finished)},
        "latency_seconds": {
            "p50": _percentile([row.get("elapsed_seconds") for row in finished
                                if row.get("elapsed_seconds") is not None], 0.5),
            "p95": _percentile([row.get("elapsed_seconds") for row in finished
                                if row.get("elapsed_seconds") is not None], 0.95)},
        "max_tokens_cap": aihubmix_study.OUTPUT_PROFILE,
        "note": "max_tokens is a configured ceiling, not a sustained-output claim; "
                "unknown-terminal requests are never resent",
        "stop_file_exists": (out / "study.STOP").exists()}
    atomic_json(out / "PROVIDER_BEHAVIOR_R3.json", behavior)
    print(json.dumps({k: behavior[k] for k in ("intents", "finished", "failed",
                                               "finish_breakdown")}, ensure_ascii=False))


def _percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(q * len(ordered)), len(ordered) - 1)
    return ordered[index]


async def main() -> None:
    global TASKS
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prereg", "m4", "m5", "ab", "provider", "closure", "ab_closure", "ab_remaining", "closure_generate",
                                          "m4_retry", "m5_retry"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--suites", type=str, default=None)
    parser.add_argument("--suffix", type=str, default=None,
                        help="cohort suffix for retry phases (fresh task ids)")
    parser.add_argument("--task-ids", type=str, default=None,
                        help="exact frozen task IDs for a new closure generation attempt")
    args = parser.parse_args()
    if args.phase == "prereg":
        phase_prereg()
    elif args.phase == "closure":
        await phase_closure(limit=args.limit, suites=args.suites and set(args.suites.split(",")),
                            sources=args.task_ids and args.task_ids.split(","),
                            suffix=args.suffix or "closure1",
                            scope="repair_" + args.suffix if args.suffix else "online")
    elif args.phase == "ab_closure":
        TASKS = read(OUT / "TASK_SET_FROZEN_R3.json")["tasks"]
        await phase_run(OUT / "closure/baseline_online", "ab", (BASELINE,),
                        limit=args.limit, suites=args.suites and set(args.suites.split(",")))
    elif args.phase == "ab_remaining":
        TASKS = unstarted_baseline_tasks(read(OUT / "TASK_SET_FROZEN_R3.json")["tasks"], OUT)
        scope = "baseline_remaining" + ("_" + args.suffix if args.suffix else "")
        await phase_run(OUT / "closure" / scope, "ab", (BASELINE,), limit=args.limit)
    elif args.phase == "closure_generate":
        if not args.task_ids or not args.suffix:
            raise ValueError("fresh closure generation requires explicit --task-ids and --suffix")
        selected_ids = set(args.task_ids.split(","))
        TASKS = [dict(task, id=task["id"] + args.suffix, repair_of=task["id"],
                      experiment_cohort="post_fix_exploratory")
                 for task in read(OUT / "TASK_SET_FROZEN_R3.json")["tasks"] if task["id"] in selected_ids]
        if len(TASKS) != len(selected_ids):
            raise ValueError("closure generation may only reuse frozen task opportunities")
        await phase_run(OUT / "closure" / ("fresh_generation_" + args.suffix), "m5", (TREATMENT,), limit=args.limit)
    elif args.phase == "m4":
        await phase_run(OUT, "m4_live_probe", (TREATMENT,), limit=1, suites={"T321"})
    elif args.phase == "m4_retry":
        # fresh cohort for cells blocked by the gateway outage (new task ids ->
        # new candidate/request ids; the BLOCKED originals stay in the denominator)
        TASKS = [dict(task, id=task["id"] + "r2") for task in TASKS
                 if not (OUT / "m4_live_probe/candidates" / (task["id"] + "-C") / "RESULT.json").exists()
                 or read(OUT / "m4_live_probe/candidates" / (task["id"] + "-C") / "RESULT.json")
                 .get("status") != "PASS"]
        await phase_run(OUT, "m4_live_probe", (TREATMENT,), limit=1, suites={"T321"})
    elif args.phase == "m5":
        await phase_run(OUT, "m5", (TREATMENT,), suites=args.suites and set(args.suites.split(",")))
    elif args.phase == "m5_retry":
        suffix = args.suffix or "r2"
        TASKS = [dict(task, id=task["id"] + suffix) for task in TASKS]
        await phase_run(OUT, "m5", (TREATMENT,), suites=args.suites and set(args.suites.split(",")))
    elif args.phase == "ab":
        await phase_run(OUT, "ab", (BASELINE,), suites=args.suites and set(args.suites.split(",")))
    elif args.phase == "provider":
        await phase_provider_behavior(OUT)


if __name__ == "__main__":
    asyncio.run(main())
