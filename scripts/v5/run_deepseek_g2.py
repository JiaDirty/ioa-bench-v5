"""Bounded official DeepSeek G2 development run; never formal generation or evaluation."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from shutil import copy2
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env
from ioabench.models import DeepSeekAdapter
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.direct_deepseek import (DirectStudy, immutable, probe, VERSION,
    generate_candidate, candidate_result)
from ioabench.v5.ai_generation.history import build_index, discover_sources, verify_sources
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.evaluation import atomic_json, writer_lock


def snapshot(out):
    digest = source_tree_hash(ROOT)
    target = out / "source_revisions" / digest
    for folder in ("src", "contracts", "config"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                dest = target / path.relative_to(ROOT)
                if dest.exists() and dest.read_bytes() != path.read_bytes():
                    raise ValueError("source snapshot changed")
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    copy2(path, dest)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    script = out / "execution_scripts" / (script_hash + ".py")
    if not script.exists():
        script.parent.mkdir(parents=True, exist_ok=True)
        copy2(__file__, script)
    return digest


def prepare_history(out):
    old_path = ROOT / "artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z/HISTORY_INDEX_V3.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    for name, digest in old["source_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("protected historical source changed: " + name)
    path = out / "history" / (source_tree_hash(ROOT) + ".json")
    if path.exists():
        index = json.loads(path.read_text(encoding="utf-8"))
    else:
        sources = {ROOT / name for name in old["discovered_sources"]}
        sources.update(path for path in discover_sources(ROOT) if not path.is_relative_to(out))
        index = build_index(ROOT, sources=sources)
        if not {row["case_sha256"] for row in old["records"]} <= {row["case_sha256"] for row in index["records"]}:
            raise ValueError("history rebuild lost retained cases")
        immutable(path, index)
    verify_sources(ROOT, index)
    immutable(out / ("HISTORY_BINDING-" + source_tree_hash(ROOT)[:12] + ".json"), {
        "history_path": path.relative_to(out).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "prior_index_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(), "summary": index["summary"],
        "findings": len(index["findings"]), "scope": "current raw disk sources plus retained bound archive extraction; no history omitted",
        "original_raw_sources_unchanged": True, "new_scientific_families": 0})
    return index


async def run(out, phase, plan=None, limit=None):
    source = snapshot(out)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    immutable(out / (phase.upper() + "_SOURCE_BINDING-" + source[:12] + "-" + script_hash[:8] + ".json"), {"version": VERSION,
        "runtime_sha256": source, "script_sha256": script_hash})
    profile = yaml.safe_load((ROOT / "config/v5/deepseek_g2_exploratory_v1.yaml").read_text(encoding="utf-8"))
    if (profile["provider"] != "deepseek" or profile["model_id"] != "deepseek-flash"
            or profile["formal_generator_allowed"] is not False or profile["formal_auditor_qualified"] is not False
            or profile["scope"] != "DEVELOPMENT_EXPLORATORY_SAME_FAMILY"):
        raise ValueError("isolated provider profile is invalid")
    immutable(out / "MODEL_AND_PARAMS.json", profile)
    if phase == "prepare":
        return prepare_history(out)["summary"]
    if phase == "settle":
        return [candidate_result(path.parent) for path in sorted((out / "candidates").glob("*/RESULT.json"))]
    load_workspace_env(ROOT / ".env")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("DEEPSEEK_API_KEY is required; value is never logged")
    port = DeepSeekAdapter(request_timeout=900)
    if (out / "MODEL_CATALOG.json").exists():
        catalog = json.loads((out / "MODEL_CATALOG.json").read_text(encoding="utf-8"))
    else:
        catalog = list(await port.discover_models())
        immutable(out / "MODEL_CATALOG.json", catalog)
    study = DirectStudy(out, port, catalog)
    if phase == "probe":
        return await probe(study)
    if phase == "generate":
        if not (out / "OFFICIAL_PROBES.json").is_file():
            raise ValueError("complete official protocol probes required")
        index = prepare_history(out)
        if plan is None:
            raise ValueError("a frozen JSON task plan is required")
        value = json.loads(plan.read_text(encoding="utf-8"))
        immutable(out / "plans" / plan.name, value)
        rows, started = [], 0
        base_references = [row["features"] for row in index["records"]]
        by_cohort = {}
        for task in value["tasks"]:
            if study.stop.exists():
                break
            result = out / "candidates" / task["id"] / "RESULT.json"
            references = by_cohort.setdefault(task.get("cohort", "pool"), list(base_references))
            if result.exists():
                row = candidate_result(result.parent)
            elif limit is not None and started >= limit:
                break
            else:
                row = await generate_candidate(study, task, index, references, workspace=ROOT)
                started += 1
                print(task["id"], row["status"], row.get("failed_stage", row["engineering_status"]), flush=True)
            rows.append(row)
            if row["status"] == "PASS":
                references.extend(case_from_dict(raw, allow_dynamic=True) for raw in
                    json.loads((result.parent / "PAIR.json").read_text(encoding="utf-8")))
        return {"processed": len(rows), "started": started, "passed": sum(row["status"] == "PASS" for row in rows)}
    raise ValueError("unknown phase")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--phase", choices=("probe", "prepare", "generate", "settle"), required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / "artifacts/v5/data_factory/direct_deepseek_g2"):
        raise ValueError("official development evidence requires its isolated root")
    with writer_lock(ROOT / "artifacts/v5/data_factory"), writer_lock(out):
        result = asyncio.run(run(out, args.phase, args.plan, args.limit))
    print(json.dumps({"phase": args.phase, "result": result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
