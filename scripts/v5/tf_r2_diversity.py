"""R2 M5 three-layer diversity metrics (05_实验与验收 §B/§E) over the R2 run.

Layers are counted independently and NEVER mixed: instance identity (case
content hash), business workflow identity (industry-abstracted binding hash)
and mechanism graph identity (existing executable structural signature). The
R1 pool is reported as separate history rows, never merged into R2 yield.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"
R1 = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"

from ioabench.v5.evaluation import atomic_json  # noqa: E402


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def candidates_under(base: Path):
    return sorted(base.glob("candidates/*/RESULT.json")) if base.exists() else []


def r1_accepted():
    baseline = read(RUN / "BASELINE_R2.json")
    return [name.removesuffix("-v12b")
            for name in baseline["r1_sealed"]["accepted_candidates_r1"]]


def layer_rows(result_paths, origin, route_default):
    rows = []
    for path in result_paths:
        result = read(path)
        directory = path.parent
        task = result.get("task", {})
        admission_path = directory.parent.parent / "reviews" / directory.name / "ADMISSION.json"
        admission = read(admission_path).get("status") if admission_path.exists() else None
        pair_path = directory / "PAIR.json"
        instance_hashes = []
        if pair_path.exists():
            pair = read(pair_path)
            from ioabench.v5.core.case import case_from_dict
            instance_hashes = [case_from_dict(case, allow_dynamic=True).content_sha256()
                               for case in pair]
        binding_path = directory / "BUSINESS_BINDING.json"
        workflow_hash = None
        industry = None
        if binding_path.exists():
            binding = read(binding_path)
            workflow_hash = binding.get("canonical_workflow_hash")
            industry = binding.get("root")
        rows.append({
            "origin": origin, "candidate": directory.name,
            "suite": task.get("suite", result.get("task", {}).get("suite")),
            "route": result.get("route", route_default),
            "status": result.get("status"),
            "failed_stage": result.get("failed_stage"),
            "admission": admission or result.get("audit_status"),
            "business_root": industry or result.get("business_root"),
            "workflow_hash": workflow_hash or result.get("business_workflow_hash"),
            "mechanism_signature": result.get("structural_signature_sha256"),
            "instance_hashes": instance_hashes})
    return rows


def main() -> int:
    rows = []
    rows += layer_rows(candidates_under(RUN / "m4_t321"), "R2", "tree_ir_runtime_v2")
    rows += layer_rows(candidates_under(RUN / "ab"), "R2", None)
    # R1 accepted pairs as separate history (never mixed into R2 yield)
    for name in r1_accepted():
        directory = R1 / "ab/candidates" / name
        result_path = directory / "RESULT.json"
        if result_path.exists():
            rows += layer_rows([result_path], "R1_HISTORY", "treatment_tree_ir")

    with (RUN / "WORKFLOW_DIVERSITY.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["origin", "suite", "workflow_hash", "candidates", "industries"])
        grouped = defaultdict(list)
        for row in rows:
            if row["workflow_hash"]:
                grouped[(row["origin"], row["suite"], row["workflow_hash"])].append(row)
        for (origin, suite, workflow_hash), items in sorted(grouped.items()):
            writer.writerow([origin, suite, workflow_hash[:16],
                             len(items), ";".join(sorted({i["business_root"] or "?"
                                                          for i in items}))])

    with (RUN / "MECHANISM_DIVERSITY.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["origin", "suite", "mechanism_signature", "instances", "candidates"])
        grouped = defaultdict(list)
        for row in rows:
            if row["mechanism_signature"]:
                grouped[(row["origin"], row["suite"], row["mechanism_signature"])].append(row)
        for (origin, suite, signature), items in sorted(grouped.items()):
            writer.writerow([origin, suite, signature[:16],
                             sum(len(i["instance_hashes"]) for i in items), len(items)])

    with (RUN / "INSTANCE_YIELD.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["origin", "suite", "route", "attempts", "engineering_pass",
                         "audited", "dev_accepted", "unique_instances"])
        grouped = defaultdict(list)
        for row in rows:
            grouped[(row["origin"], row["suite"], row["route"])].append(row)
        for (origin, suite, route), items in sorted(grouped.items()):
            instances = {h for i in items for h in i["instance_hashes"]}
            writer.writerow([origin, suite, route, len(items),
                             sum(i["status"] == "PASS" for i in items),
                             sum(bool(i["admission"]) for i in items),
                             sum(i["admission"] == "DEV_ACCEPTED" for i in items),
                             len(instances)])

    accepted_r2 = [row["candidate"] for row in rows
                   if row["origin"] == "R2" and row["admission"] == "DEV_ACCEPTED"]
    summary = {"version": "ioabench.v5.r2-diversity/1.0.0", "generated_utc": utc(),
               "r2_dev_accepted": accepted_r2,
               "r1_history_accepted": r1_accepted(),
               "t362_r1_same_signature_fact":
                   "R1 T362-t2-T/T362-t2-B share one mechanism signature (historical "
                   "fact retained); R2 counts instances and mechanisms separately",
               "rows": len(rows)}
    atomic_json(RUN / "DIVERSITY_SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
