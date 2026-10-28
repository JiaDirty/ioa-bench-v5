"""Fixed three-fragment repair comparison; no judge qualification or formal data selection."""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.config.loader import load_workspace_env
from ioabench.models import AIHubMixAdapter, ModelRequest
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import program_proposal, proposal_contract
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryRouter, classify_provider_failure, redact
from ioabench.v5.ai_generation.factory import decode_json
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.evaluation import atomic_json, writer_lock
from compare_auxiliary_models import contract_for, immutable, read, sha, checked_result, validate_candidate, TARGETS


def repair_tasks():
    tasks = []
    for suite, field, bad in [("T321", "item_count", 0), ("T331", "fanout_width", 4), ("T352", "reputation_rating", 6)]:
        spec = suite_spec(suite, typed=True)
        blueprint = program_proposal(spec, seed=38101, difficulty="M", target=TARGETS[suite][0])
        invalid = deepcopy(blueprint)
        invalid["suite_payload"][field] = bad
        findings = list(spec.adapter.validate_blueprint(invalid))
        assert findings, "negative fixture must be rejected before asking any model"
        tasks.append({"suite": suite, "id": suite.lower() + "-fixed-repair", "seed": 38101, "field": field,
            "invalid_blueprint": invalid, "findings": findings,
            "contract": proposal_contract(spec, seed=38101, difficulty="M")})
    return tasks


async def run(output, preflight, study):
    tasks = repair_tasks()
    matrix = read(study / "MODEL_CAPABILITY_MATRIX.json")["models"]
    plan = {"version": "ioabench.v5.fixed-repair-comparison/1.0.0", "models": [row["requested_model_id"] for row in matrix],
        "tasks": tasks, "attempts_per_task": 1, "output_budget": 16384, "source_sha256": source_tree_hash(ROOT),
        "script_sha256": sha(Path(__file__)), "scope": "isolated developer repair only; all fixtures fail before calls",
        "formal_SUT_used": False, "auditor_role_qualification": "BLOCKED_PI_GOLD_DISPOSITION_REQUIRED"}
    immutable(output / "PREREGISTRATION.json", plan)
    result_path = output / "REPAIR_COMPARISON.json"
    if result_path.exists():
        report = checked_result(result_path)
        return report
    load_workspace_env(ROOT / ".env")
    port = AIHubMixAdapter(base_url="https://api.inferera.com/v1", request_timeout=900, stop_on_provider_error=True)
    catalog = read(preflight / "MODEL_CATALOG.json")
    semaphore, auth_stop = asyncio.Semaphore(2), asyncio.Event()
    async def one(model_row):
        model = model_row["requested_model_id"]
        protocol = next((row["protocol"] for row in model_row["protocols"] if row["json"] == "PASS"), None)
        rows, blocked = [], None
        for task in tasks:
            directory = output / model / task["id"]
            result = directory / "RESULT.json"
            if result.exists():
                rows.append(checked_result(result))
                continue
            row = {"model_id": model, "task_id": task["id"], "suite": task["suite"], "status": "NOT_RUN",
                   "machine_qualified": False, "formal_accepted": False}
            if not protocol or blocked or auth_stop.is_set():
                row["reason"] = blocked or "protocol/credential unavailable"
            else:
                contract = contract_for(preflight, model, protocol=protocol)
                router = AuxiliaryRouter(port, [contract], catalog, directory / "model_io")
                schema = {"type": "object", "additionalProperties": False, "required": ["path", "value"], "properties": {
                    "path": {"const": "/suite_payload/" + task["field"]}, "value": {"type": "number"}}}
                messages = [{"role": "system", "content": "Repair only the specified invalid structural field. Return the exact JSON patch object; preserve all other fields and program-owned truth."},
                    {"role": "user", "content": json.dumps({"task": task, "output_schema": schema}, ensure_ascii=False)}]
                try:
                    async with semaphore:
                        if auth_stop.is_set():
                            raise ValueError("credential stopped before request")
                        response = await router.invoke(contract.profile.role, "fixed-repair", ModelRequest(messages, {}))
                    patch = decode_json(response.text)
                    from jsonschema import Draft202012Validator
                    Draft202012Validator(schema).validate(patch)
                    repaired = deepcopy(task["invalid_blueprint"])
                    repaired["suite_payload"][task["field"]] = patch["value"]
                    # Integer fields must remain integers; never coerce model output to make it pass.
                    atomic_json(directory / "REPAIR.json", patch)
                    result = await asyncio.to_thread(validate_candidate, directory, {"id": task["id"], "suite": task["suite"], "seed": task["seed"]}, repaired)
                    row.update(status="PASS", engineering=result, actual_parameters=dict(contract.parameters))
                except Exception as exc:
                    category = classify_provider_failure(exc)
                    row.update(status="FAIL", category=category, error_type=type(exc).__name__, error=redact(str(exc)))
                    if category in {"AUTH/PERMISSION", "MISSING_SECRET"}:
                        auth_stop.set()
                    if category in {"AUTH/PERMISSION", "MISSING_SECRET", "NETWORK_TRANSIENT", "PROVIDER_UNAVAILABLE"}:
                        blocked = category
            row["evidence_sha256"] = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*")
                if p.is_file() and p.name != "RESULT.json" and not p.name.endswith(".lock")}
            atomic_json(directory / "RESULT.json", row)
            rows.append(row)
        return rows
    rows = [row for group in await asyncio.gather(*(one(model) for model in matrix)) for row in group]
    assert source_tree_hash(ROOT) == plan["source_sha256"], "runtime changed during fixed repair comparison"
    report = {"status": "PARTIAL_DEVELOPMENT_ONLY", "planned": len(matrix) * 3, "rows": rows,
        "passed": sum(row["status"] == "PASS" for row in rows), "machine_qualified": 0,
        "evidence_sha256": {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*")
            if p.is_file() and p.name != "REPAIR_COMPARISON.json" and not p.name.endswith(".lock")}}
    atomic_json(result_path, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--study", type=Path, required=True)
    args = parser.parse_args()
    with writer_lock(args.out):
        result = asyncio.run(run(args.out, args.preflight, args.study))
    print(json.dumps({key: result[key] for key in ("status", "planned", "passed")}))
