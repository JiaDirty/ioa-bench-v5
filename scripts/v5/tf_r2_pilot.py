"""R2 online pilot: T321 first (M4), then T331/T362 and the same-task A/B (M5).

Every candidate runs the mandatory Tree→BusinessBinding→MechanismIR→Compiler
chain on the treatment route (``tree_ir_runtime_v2``); the frozen
``baseline_4stage`` route stays available as the read-only comparison arm. New
run scope, new task/candidate ids, new request ids; the sealed R1 stop/ledger
and the 7 accepted R1 pairs are read-only history that the dedup index EXTENDS
(never rewrites). No USD budget stop (user-authorized); usage is still recorded.
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

OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"
R1 = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
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
# Fresh ids/seeds/target cells (R1 used seeds 2024-2026; R2 uses 3xx seeds and
# target combos chosen for structural distance from the R1 pool).
TASKS = [
    {"id": "R2-T321-x1", "suite": "T321", "seed": 301, "difficulty": "M", "effort": "high",
     "target": {"close_gate": "profile_verified"}, "assertions": ["T321-A1"],
     "industry": "industry.medicine_supply"},
    {"id": "R2-T321-x2", "suite": "T321", "seed": 302, "difficulty": "M", "effort": "high",
     "target": {"broker_count": 3, "peer_profile_delivery": "broker_gamma",
                "offer_access": "broker_query", "close_gate": "profile_verified",
                "renegotiation_window": "after_final_delivery", "offer_profiles": T321_FULL},
     "assertions": ["T321-A1", "T321-A2"], "industry": "industry.payment_clearing"},
    {"id": "R2-T321-x3", "suite": "T321", "seed": 303, "difficulty": "H", "effort": "high",
     "target": {"broker_count": 3, "peer_profile_delivery": "broker_gamma",
                "renegotiation_window": "after_final_delivery", "offer_profiles": T321_FULL},
     "assertions": ["T321-A2"], "industry": "industry.medicine_supply"},
    {"id": "R2-T331-x1", "suite": "T331", "seed": 311, "difficulty": "M", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation"}, "assertions": ["T331-A1"],
     "industry": "industry.payment_clearing"},
    {"id": "R2-T331-x2", "suite": "T331", "seed": 312, "difficulty": "M", "effort": "high",
     "target": {"confirmation_loop": "terminal_receipt_notes", "propagation_topology": "chain"},
     "assertions": ["T331-A2"], "industry": "industry.medicine_supply"},
    {"id": "R2-T331-x3", "suite": "T331", "seed": 313, "difficulty": "H", "effort": "high",
     "target": {"rebroadcast_timing": "after_propagation", "confirmation_loop": "terminal_receipt_notes",
                "propagation_topology": "chain", "fanout_width": 3},
     "assertions": ["T331-A1", "T331-A2"], "industry": "industry.payment_clearing"},
    {"id": "R2-T362-x1", "suite": "T362", "seed": 321, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "source_release": "per_owner_turn"},
     "assertions": ["T362-A1"], "industry": "industry.payment_clearing"},
    {"id": "R2-T362-x2", "suite": "T362", "seed": 322, "difficulty": "M", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                "evidence_release": "after_alert", "relay_before_digest": "required"},
     "assertions": ["T362-A2"], "industry": "industry.medicine_supply"},
    {"id": "R2-T362-x3", "suite": "T362", "seed": 323, "difficulty": "H", "effort": "high",
     "target": {"evidence_access": "record_query", "evidence_flow": "split_sources",
                "evidence_release": "after_alert", "source_release": "per_owner_turn"},
     "assertions": ["T362-A1"], "industry": "industry.payment_clearing"},
]
ROUTES = ("tree_ir_runtime_v2", "baseline_4stage")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


async def study_for(out: Path):
    load_workspace_env(ROOT / ".env")
    import os
    if not os.environ.get("AIHUBMIX_API_KEY"):
        raise ValueError("AIHUBMIX_API_KEY missing; no value logged")
    port = AIHubMixAdapter(stop_on_provider_error=True, request_timeout=1800)
    catalog_path = out / "MODEL_CATALOG.json"
    catalog = read(catalog_path) if catalog_path.exists() else list(await port.discover_models())
    atomic_json(catalog_path, catalog)
    return aihubmix_study.AihubmixStudy(out, port, catalog)


def r1_accepted_candidates() -> list[str]:
    baseline = read(OUT / "BASELINE_R2.json")
    return [name.removesuffix("-v12b") for name in baseline["r1_sealed"]["accepted_candidates_r1"]]


def load_index():
    """Sealed 18-suite history + the 7 R1 accepted pairs (read-only extension)."""
    from ioabench.v5.ai_generation.history import build_index
    from copy import deepcopy
    index = deepcopy(read(SEALED_INDEX))
    for candidate in r1_accepted_candidates():
        pair = R1 / "ab/candidates" / candidate / "PAIR.json"
        if not pair.is_file():
            continue
        addition = build_index(ROOT, sources=[pair])
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


def extend_index(index, directory: Path):
    from copy import deepcopy
    from ioabench.v5.ai_generation.history import build_index
    merged = deepcopy(index)
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


async def audit_one(study, source: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    review = await audit_pair(study, source, destination / "audit", protocol=PROTOCOL_V12,
                              max_tokens=aihubmix_study.OUTPUT_PROFILE["base_max_tokens"])
    pair = read(source / "PAIR.json")
    control = next(case_from_dict(case, allow_dynamic=True) for case in pair if case["arm"] == "CONTROL")
    record = admission(source, review, __import__(
        "ioabench.v5.ai_generation.development", fromlist=["structure_vector"]).structure_vector(control),
        audit_directory=destination / "audit")
    atomic_json(destination / "ADMISSION.json", record)
    return record


async def run_candidates(study, tasks, out_sub, routes, index, policy, *, limit=None,
                         skip_cells=frozenset()):
    references = [row["features"] for row in index["records"]]
    rows, started, accepted = [], 0, []
    for route in routes:
        for task in tasks:
            candidate_id = task["id"] + ("-T" if route.startswith("tree") else "-B")
            if (task["id"], route) in skip_cells:
                continue
            directory = out_sub / "candidates" / candidate_id
            if study.stop.exists():
                rows.append({"task": task["id"], "route": route, "candidate": candidate_id,
                             "status": "NOT_RUN_GLOBAL_STOP"})
                continue
            if (directory / "RESULT.json").exists():
                result = read(directory / "RESULT.json")
            else:
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
                    record = await audit_one(study, directory, out_sub / "reviews" / candidate_id)
                except Exception as exc:
                    category = classify_provider_failure(exc)
                    record = {"audit_status": "AUDIT_REQUEST_FAILED", "status": "QUARANTINED",
                              "hard_gate_errors": [f"{type(exc).__name__}:{category}"],
                              "recorded_strict_replays": 0, "history_scope": "FULL_HISTORY"}
                    if category not in {"REQUEST_UNRESOLVED", "UNKNOWN", "AUTH/PERMISSION",
                                        "INSUFFICIENT_BALANCE", "MISSING_SECRET"}:
                        record["hard_gate_errors"] = [f"{type(exc).__name__}:local"]
                if record.get("status") == "DEV_ACCEPTED":
                    index = extend_index(index, directory)
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
        if study.stop.exists():
            break
    return rows, accepted, index


def write_denominator(out_sub, rows, accepted):
    with (out_sub / "FAILURE_FUNNEL.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["stage", "count"])
        for stage, count in sorted(Counter(
                row.get("failed_stage") or row["status"] for row in rows).items()):
            writer.writerow([stage, count])
    with (out_sub / "AB_RESULTS.csv").open("w", encoding="utf-8", newline="") as stream:
        fieldnames = ["task", "route", "candidate", "status", "failed_stage", "error_type",
                      "audit_status", "admission", "history_statuses", "business_root",
                      "business_workflow_hash", "source"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "history_statuses": ";".join(row.get("history_statuses") or []),
                             "source": row.get("source", "ab")})
    ledger = OUT / "REQUEST_LEDGER.jsonl"
    finished = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()] \
        if ledger.exists() else []
    atomic_json(out_sub / "RUN_SUMMARY.json", {
        "rows": rows, "accepted_new_pairs": accepted,
        "counter": dict(Counter(row["status"] for row in rows)),
        "paid_completions": sum(row.get("event") == "REQUEST_FINISHED" for row in finished),
        "finish_length": sum(
            (row.get("parameters") or {}).get("max_tokens") is not None and row.get("event") == "REQUEST_FAILED"
            for row in finished)})


async def phase_t321(out: Path):
    study = await study_for(out)
    if study.stop.exists():
        raise ValueError("study stopped; no new paid requests")
    index = load_index()
    tasks = [task for task in TASKS if task["suite"] == "T321"]
    rows, accepted, index = await run_candidates(study, tasks, out / "m4_t321",
                                                 ("tree_ir_runtime_v2",), index,
                                                 validate_policy(dict(POLICY)))
    write_denominator(out / "m4_t321", rows, accepted)
    atomic_json(out / "m4_t321/M4_SUMMARY.json", {
        "t321_new_dev_accepted": accepted, "rows": rows,
        "goal": "at least one fresh T321 DEV_ACCEPTED pair on the R2 chain"})
    print(json.dumps({"m4_t321_accepted": accepted}, ensure_ascii=False))


async def phase_ab_repair(out: Path):
    """Rerun the baseline cells that failed through the R2 schema leak (the
    business_binding key was visible to the frozen 4-stage prompts before the
    acquisition fix). Fresh candidate ids; the failed originals stay sealed in
    the denominator as leak-attributable engineering failures."""
    study = await study_for(out)
    index = load_index()
    # dedup against every accepted pair of this run (treatment + baseline + m4)
    accepted_dirs = [path.parent for path in sorted((out / "ab/reviews").glob("*/ADMISSION.json"))
                     if read(path).get("status") == "DEV_ACCEPTED"]
    accepted_dirs += [path.parent for path in sorted((out / "m4_t321/reviews").glob("*/ADMISSION.json"))
                      if read(path).get("status") == "DEV_ACCEPTED"]
    for directory in accepted_dirs:
        candidate = directory.name
        if (out / "ab/candidates" / candidate / "PAIR.json").exists():
            index = extend_index(index, out / "ab/candidates" / candidate)
        elif (out / "m4_t321/candidates" / candidate / "PAIR.json").exists():
            index = extend_index(index, out / "m4_t321/candidates" / candidate)
    repairs = []
    for original in ("R2-T321-x1", "R2-T321-x2", "R2-T331-x1", "R2-T331-x3"):
        task = next(item for item in TASKS if item["id"] == original)
        repairs.append(dict(task, id=original + "-Br2"))
    rows, accepted, index = await run_candidates(study, repairs, out / "ab",
                                                 ("baseline_4stage",), index,
                                                 validate_policy(dict(POLICY)))
    write_denominator(out / "ab", rows, accepted)
    atomic_json(out / "ab/BASELINE_REPAIRS.json", {
        "reason": "originals failed through the R2 schema leak (BINDING_INVALID: model-"
                  "written business_binding under the frozen 4-stage prompts)",
        "fixed_by": "acquisition.staged_proposal strips the program-owned key",
        "repairs": rows})
    print(json.dumps({"repairs_accepted": accepted}, ensure_ascii=False))


async def phase_ab(out: Path, *, limit=None):
    study = await study_for(out)
    index = load_index()
    # The T321 treatment opportunities already ran in M4: reuse those sealed
    # results/admissions as the A/B treatment arm instead of paying for a second
    # sample of the same cell. The duplicated ab/candidates/R2-T321-x1-T attempt
    # (stopped mid-audit by the operator) stays on disk, quarantined; its
    # unresolved audit request id is never resent.
    prefilled, skip = [], set()
    m4 = out / "m4_t321"
    if m4.exists():
        for path in sorted((m4 / "candidates").glob("*/RESULT.json")):
            result = read(path)
            candidate = path.parent.name
            admission_path = m4 / "reviews" / candidate / "ADMISSION.json"
            record = read(admission_path) if admission_path.exists() else {}
            prefilled.append({"task": candidate.rsplit("-", 1)[0], "route": "tree_ir_runtime_v2",
                              "candidate": candidate, "status": result["status"],
                              "failed_stage": result.get("failed_stage"),
                              "error_type": result.get("error_type"),
                              "audit_status": record.get("audit_status"),
                              "admission": record.get("status"),
                              "history_statuses": result.get("history_statuses"),
                              "business_root": result.get("business_root"),
                              "business_workflow_hash": result.get("business_workflow_hash"),
                              "source": "m4_t321_reused"})
            skip.add((candidate.rsplit("-", 1)[0], "tree_ir_runtime_v2"))
            if record.get("status") == "DEV_ACCEPTED":
                index = extend_index(index, path.parent)
    duplicated = out / "ab/candidates/R2-T321-x1-T"
    if duplicated.exists() and not (duplicated / "NOTE_SUPERSEDED.json").exists():
        atomic_json(duplicated / "NOTE_SUPERSEDED.json", {
            "note": "duplicated the M4 cell; operator stopped its audit mid-flight; "
                    "the sent-but-unknown-terminal request id below is NEVER resent",
            "unresolved_request_id": "audit-high-5be53da31c7a2100",
            "superseded_by": "m4_t321/candidates/R2-T321-x1-T"})
    tasks = TASKS  # skip_cells drops only the reused treatment cells per task
    rows, accepted, index = await run_candidates(study, tasks, out / "ab", ROUTES, index,
                                                 validate_policy(dict(POLICY)), limit=limit,
                                                 skip_cells=skip)
    rows = prefilled + rows
    accepted = [row["candidate"] for row in prefilled
                if row["admission"] == "DEV_ACCEPTED"] + accepted
    write_denominator(out / "ab", rows, accepted)
    print(json.dumps({"ab_accepted": accepted}, ensure_ascii=False))


def phase_prereg(out: Path):
    frozen = {"version": "ioabench.v5.r2-task-set/1.0.0", "frozen_at_utc": utc(),
              "tasks": TASKS, "routes": list(ROUTES),
              "baseline_expected_head": "49d096e20f6db160130ece6d78220aff7d2bd53f",
              "history_base": {"sealed_index_sha256": __import__("hashlib").sha256(
                  SEALED_INDEX.read_bytes()).hexdigest(),
                               "plus_r1_accepted_candidates": r1_accepted_candidates()},
              "model": {"provider": aihubmix_study.PROVIDER, "model_id": aihubmix_study.MODEL,
                        "effort_default": "high", "effort_complex": "max"},
              "output_profile": aihubmix_study.OUTPUT_PROFILE,
              "budget_gate": "DISABLED_USER_AUTHORIZED",
              "audit": {"protocol": PROTOCOL_V12, "efforts": ["high", "max"],
                        "max_tokens": aihubmix_study.OUTPUT_PROFILE["base_max_tokens"]},
              "dedup_threshold": 0.9, "history_scope": "FULL_HISTORY_PLUS_R1",
              "runtime_sha256": source_tree_hash(ROOT)}
    atomic_json(out / "TASK_SET_FROZEN.json", frozen)
    atomic_json(out / "AB_PREREGISTRATION.json", {
        "version": "ioabench.v5.r2-preregistration/1.0.0", "frozen_at_utc": utc(),
        "task_set_sha256": canonical_sha256(frozen),
        "treatment": "tree_ir_runtime_v2: TreeSelection -> BusinessBinding -> MechanismIR.validate==[] "
                     "-> capability.validate_binding -> blueprint_from_ir -> existing compilers -> "
                     "full gates -> protocol-1.2 two-effort audit",
        "baseline": "frozen baseline_4stage staged_proposal (read-only comparison arm)",
        "comparison_claim": "system-level yield comparison across routes with different call "
                            "structures; NOT a single-factor Tree/IR causal estimate "
                            "(offline ablation covers the factor attribution)",
        "same_gates": ["compile_and_gate", "reference execution matrix", "oracle firewall",
                       "execution fidelity + design-assertion + business witnesses",
                       "full-history dedup 0.9", "strict replay >=6", "protocol-1.2 audit",
                       "development admission"],
        "formal_accepted": False})
    print(json.dumps({"frozen_tasks": len(TASKS)}))


def _row_from_result(result_path: Path, out_sub: Path):
    result = read(result_path)
    directory = result_path.parent
    candidate = directory.name
    admission_path = out_sub / "reviews" / candidate / "ADMISSION.json"
    record = read(admission_path) if admission_path.exists() else {}
    return {"task": candidate.rsplit("-", 1)[0], "route": result.get("route", "baseline_4stage"),
            "candidate": candidate, "status": result["status"],
            "failed_stage": result.get("failed_stage"), "error_type": result.get("error_type"),
            "audit_status": record.get("audit_status"), "admission": record.get("status"),
            "history_statuses": result.get("history_statuses"),
            "business_root": result.get("business_root"),
            "business_workflow_hash": result.get("business_workflow_hash"),
            "source": out_sub.name}


def phase_reports(out: Path):
    """Zero-call rebuild of the run's denominators from sealed results."""
    rows, accepted = [], []
    for sub in ("m4_t321", "ab"):
        base = out / sub
        if not (base / "candidates").exists():
            continue
        for result_path in sorted((base / "candidates").glob("*/RESULT.json")):
            row = _row_from_result(result_path, base)
            if (result_path.parent / "NOTE_SUPERSEDED.json").exists():
                row["source"] = "ab_superseded_duplicate"
            rows.append(row)
            if row["admission"] == "DEV_ACCEPTED":
                accepted.append(row["candidate"])
    write_denominator(out / "ab", rows, accepted)
    print(json.dumps({"rows": len(rows), "accepted": accepted}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True,
                        choices=("prereg", "t321", "ab", "ab_repair", "reports"))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.phase == "prereg":
        phase_prereg(OUT)
    elif args.phase == "t321":
        asyncio.run(phase_t321(OUT))
    elif args.phase == "ab_repair":
        asyncio.run(phase_ab_repair(OUT))
    elif args.phase == "reports":
        phase_reports(OUT)
    else:
        asyncio.run(phase_ab(OUT, limit=args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
