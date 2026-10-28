"""Frozen same-task effort comparison; development outputs never enter formal production."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.config.loader import load_workspace_env
from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import staged_proposal
from ioabench.v5.ai_generation.factory import decode_json
from ioabench.v5.ai_generation.model_routing import auxiliary_parameters
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.evaluation import atomic_json
from benchmark_provider_round02 import Study, _effort
from compare_auxiliary_models import TARGETS, immutable, read, sha, validate_candidate


def prepare(out):
    base = read(out / "PROTOCOL_PLAN.json")
    configs = []
    supplemental = read(out / "SUPPLEMENTAL_CONFIGS.json") if (out / "SUPPLEMENTAL_CONFIGS.json").exists() else []
    for config in base["configs"] + supplemental:
        batch = "p1-native" if config in supplemental else "p1"
        result = out / "protocols" / config["id"] / batch / "RESULT.json"
        if not result.exists() or read(result)["status"] != "PASS":
            continue
        schema = read(out / "schemas" / (config["model"] + ".json"))
        catalog = read(out / "MODEL_CATALOG.json")
        entry = next(row for row in catalog if (row.get("model_id") or row.get("id")) == config["model"])
        options = schema.get("specs", {}).get("reasoning_options", [])
        levels = next((item["values"] for item in options if item["type"] == "effort"), [None])
        for level in levels:
            if level not in (None, "none", "low", "medium", "high", "xhigh", "max"):
                continue
            parameters = auxiliary_parameters(schema, protocol=config["protocol"], effort=level, output_budget=4096,
                                              catalog_entry=entry)
            if schema["vendor"] == "anthropic":
                parameters["thinking"] = {"type": "adaptive"}
            if config["model"] == "minimax-m3":
                parameters["thinking"] = {"type": "adaptive"}
            if schema["vendor"] == "deepseek" and level == "none":
                parameters["thinking"] = {"type": "disabled"}
            configs.append({**config, "id": config["model"] + "--" + (level or "enabled-default"),
                            "parameters": parameters})
        if schema["vendor"] == "xiaomi":
            parameters = {**config["parameters"], "thinking": {"type": "disabled"}}
            configs.append({**config, "id": config["model"] + "--disabled", "parameters": parameters})
    tasks = [{"id": f"{suite}-q{index+1}", "suite": suite, "seed": 820201 + index,
              "difficulty": "M", "target": TARGETS[suite][index*3]}
             for suite in ("T321", "T331", "T352") for index in range(2)]
    tasks += [
        {"id": "evidence-contradiction", "prompt": "Return JSON {\"source\":id,\"stock\":integer}. "
         "Inventory for one lot has signed revision 7 by warehouse owner: stock=18. A reseller repeats revision 4: stock=80. "
         "Public popularity is not revision authority. IDs are owner7 and reseller4. Which current record should be used?",
         "expected": {"source": "owner7", "stock": 18}},
        {"id": "causal-repair", "prompt": "Return JSON {\"actions\":[strings]}. "
         "A stale revision was copied into downstream inventories. Choose minimal actions in order from "
         "pause_forwarding, verify_owner_revision, correct_downstream, resume_forwarding, erase_logs, change_truth. "
         "Need stop further stale spread, establish authoritative latest revision, correct copies and restore delivery; preserve logs and truth.",
         "expected": {"actions": ["pause_forwarding", "verify_owner_revision", "correct_downstream", "resume_forwarding"]}},
    ]
    plan = {"version": "ioabench.v5.round02-effort-comparison/1.0.0", "configs": configs, "tasks": tasks,
            "Q_budget": 16384, "R_batches": ["r1", "r2"], "R_order": "each full batch completes before next",
            "max_concurrency": 3, "max_attempts_per_task": 1, "seed": 820201,
            "selection_weights": {"valid_pair_yield": .35, "behavioral_quality": .25, "availability": .20,
                                  "realized_cost_per_valid_pair": .10, "latency": .10},
            "history": "current supported disk plus previously extracted archives; both arms; no threshold change",
            "scientific_holdout_used": False, "auditor_qualified": False, "formal_production": False}
    immutable(out / "BENCHMARK_TASKSET_FROZEN.json", plan)
    return plan


async def quality(study, config, task):
    directory = study.out / "quality" / config["id"] / task["id"]
    result_path = directory / "RESULT.json"
    if result_path.exists():
        return read(result_path)
    params = dict(config["parameters"])
    for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
        if key in params:
            params[key] = 16384
    qconfig = {**config, "parameters": params}
    row = {"config_id": config["id"], "model": config["model"], "task": task["id"], "status": "NOT_RUN",
           "machine_qualified": False, "started_utc": datetime.now(timezone.utc).isoformat()}
    try:
        if "suite" in task:
            async def call(name, messages):
                response = await study.invoke(qconfig, directory / "model_io", name, messages)
                return {**asdict(response), "resolved_model_id": config["model"]}
            proposal, stages = await staged_proposal(suite_spec(task["suite"], typed=True), seed=task["seed"],
                difficulty=task["difficulty"], target=task["target"], call=call, decode=decode_json)
            atomic_json(directory / "STAGES.json", stages)
            row.update(await asyncio.to_thread(validate_candidate, directory, task, proposal))
            from ioabench.v5.ai_generation.history import classify
            from ioabench.v5.core.case import case_from_dict
            binding = read(study.out / "QUALITY_EXECUTION_BINDING.json")
            index = read(study.out / binding["history_path"])
            spec = suite_spec(task["suite"], typed=True)
            history = [classify(case_from_dict(case, allow_dynamic=True), index, scenario=spec.scenario_factory())
                       for case in read(directory / "PAIR.json")]
            atomic_json(directory / "HISTORY.json", history)
            row["nonduplicate"] = all(item["status"] in {"VALID_FAMILY_INSTANCE", "VERIFIED_NEW_FAMILY"} for item in history)
            row["history_status"] = [item["status"] for item in history]
            if not row["nonduplicate"]:
                row["status"] = "REJECTED_HISTORY"
        else:
            response = await study.invoke(qconfig, directory / "model_io", task["id"],
                [{"role": "user", "content": task["prompt"]}])
            if decode_json(response.text) != task["expected"]:
                raise ValueError("MODEL_QUALITY: deterministic task answer mismatch")
            row["status"] = "PASS"
    except Exception as exc:
        row.update(status="FAIL", error_type=type(exc).__name__, error=str(exc),
                   stage=getattr(exc, "stage", None), findings=getattr(exc, "findings", None))
    row["completed_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_json(result_path, row)
    return row


async def run(out, phase):
    plan = prepare(out)
    if phase == "quality":
        history = out / "HISTORY_INDEX_V3.json"
        if not history.exists():
            raise ValueError("quality requires the final-source historical index")
        immutable(out / "QUALITY_EXECUTION_BINDING.json", {"runtime_source_sha256": source_tree_hash(ROOT),
            "taskset_sha256": sha(out / "BENCHMARK_TASKSET_FROZEN.json"), "history_path": history.name,
            "history_sha256": sha(history), "script_sha256": sha(Path(__file__))})
    load_workspace_env(ROOT / ".env")
    study = Study(out, AIHubMixAdapter(base_url="https://api.inferera.com/v1", stop_on_provider_error=True,
                                      request_timeout=900))
    configs = list(plan["configs"])
    random.Random(plan["seed"]).shuffle(configs)
    semaphore = asyncio.Semaphore(plan["max_concurrency"])
    async def one(config, batch=None):
        async with semaphore:
            if study.stop_path.exists():
                return
            if batch:
                row = await study.protocol(config, batch)
                print(config["id"], batch, row["status"], flush=True)
            else:
                for task in plan["tasks"]:
                    if study.stop_path.exists():
                        break
                    result = out / "protocols" / config["id"] / "r2/RESULT.json"
                    if not result.exists() or read(result)["status"] != "PASS":
                        break
                    row = await quality(study, config, task)
                    print(config["id"], task["id"], row["status"], flush=True)
    if phase == "reliability":
        for batch in plan["R_batches"]:
            if study.stop_path.exists():
                break
            atomic_json(out / (batch + "_START.json"), {"at_utc": datetime.now(timezone.utc).isoformat()})
            await asyncio.gather(*(one(config, batch) for config in configs))
            atomic_json(out / (batch + "_END.json"), {"at_utc": datetime.now(timezone.utc).isoformat()})
    elif phase == "quality":
        await asyncio.gather(*(one(config) for config in configs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--phase", choices=("prepare", "reliability", "quality"), required=True)
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare(args.out)
    else:
        asyncio.run(run(args.out, args.phase))


if __name__ == "__main__":
    main()
