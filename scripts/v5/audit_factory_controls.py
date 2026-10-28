"""Run a fixed reviewer-control set once; resume only exact durable responses."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.factory import recorded_call, read_json, decode_json
from ioabench.v5.ai_generation.judge_controls import fixed_controls, score_control, summarize_controls
from ioabench.v5.ai_generation.model_routing import auxiliary_chat_parameters
from ioabench.v5.ai_generation.auxiliary_runtime import usage_cost
from ioabench.v5.ai_generation.quality import review_prompt, compile_semantic_review
from ioabench.v5.evaluation import atomic_json, safe_id
from routed_t321_data_factory_s1 import _load_api_key, _lock
from data_factory import archive_source


async def audit(directory: Path, model_id: str, prepare_only: bool = False, *, preflight: Path | None = None):
    runtime_hash = source_tree_hash(ROOT)
    controls_path = directory / "GOLD_CONTROLS.json"
    if controls_path.exists():
        controls = read_json(controls_path)
    else:
        controls = await asyncio.to_thread(fixed_controls)
        atomic_json(controls_path, controls)
    source_files = [Path(__file__), ROOT / "src/ioabench/v5/ai_generation/judge_controls.py",
                    ROOT / "src/ioabench/v5/ai_generation/quality.py"]
    source = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
    if source_tree_hash(ROOT) != runtime_hash:
        raise ValueError("runtime changed while constructing reviewer controls")
    contract = {"auditor": model_id, "controls_sha256": canonical_sha256(controls), "source": source,
                "runtime_source_sha256": runtime_hash,
                "preflight": str(preflight.resolve()) if preflight else None,
                "scientific_acceptance": False, "formal_frozen_SUT_changed": False}
    path = directory / "CONTROL_CONTRACT.json"
    if path.exists() and read_json(path) != contract:
        raise ValueError("control contract changed; use a new versioned run")
    atomic_json(path, contract)
    archive_source(directory)
    result_path = directory / "CONTROL_RESULT.json"
    if result_path.exists():
        report = read_json(result_path)
        for name, digest in report["evidence_sha256"].items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError("control evidence changed: " + name)
        return report
    if prepare_only:
        return {"status": "PREPARED_NOT_AUDITED", "provider_calls": 0, "passed": False}
    if preflight is None:
        raise ValueError("a real successful exact-ID preflight is required before gold audit")
    prepared = read_json(preflight / "AIHUBMIX_PREFLIGHT.json")
    row = next(item for item in prepared["candidates"] if item.get("requested_model_id") == model_id)
    if row.get("live_probe") != "PASS":
        raise ValueError("model has not passed its real minimum probe")
    probe_path = Path(row["response_evidence"])
    if not probe_path.is_absolute():
        probe_path = ROOT / probe_path
    probe = read_json(probe_path)
    if canonical_sha256(probe["response"]) != probe["response_sha256"]:
        raise ValueError("preflight response evidence changed")
    contract["preflight_result_sha256"] = hashlib.sha256((preflight / "AIHUBMIX_PREFLIGHT.json").read_bytes()).hexdigest()
    # The immutable run contract above binds the path; exact evidence is separately retained.
    atomic_json(directory / "PREFLIGHT_BINDING.json", {"sha256": contract["preflight_result_sha256"], "candidate": row})
    endpoint = row["endpoint"].removesuffix("/chat/completions")
    catalog = tuple(read_json(preflight / "MODEL_CATALOG.json"))
    schema = read_json(preflight / "schemas" / (model_id + ".json"))
    if schema is None:
        raise ValueError("verified exact auditor schema required")
    atomic_json(directory / "MODEL_CATALOG.json", catalog)
    atomic_json(directory / "MODEL_SCHEMA.json", schema)
    entry = next(item for item in catalog if (item.get("model_id") or item.get("id")) == model_id)
    profile = ModelProfile("aihubmix", model_id, {}, {}, role="INDEPENDENT_AUDITOR")
    parameters = auxiliary_chat_parameters(schema)
    if parameters != row["actual_parameters"]:
        raise ValueError("new documented full-parameter preflight required")
    atomic_json(directory / "PARAMETER_BINDING.json", {"actual_parameters": parameters,
        "preflight_result_sha256": contract["preflight_result_sha256"]})
    port = AIHubMixAdapter(api_key=_load_api_key(), base_url=endpoint, stop_on_provider_error=True, request_timeout=900)
    for path in source_files:
        target = directory / "source" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError("archived control source changed")
        target.write_bytes(path.read_bytes())
    rows, usage, costs = [], [], []
    for control in controls:
        target = directory / control["id"]
        request = ModelRequest(review_prompt(control["view"]), parameters, role_metadata={"role": "INDEPENDENT_AUDITOR"})
        try:
            response = await recorded_call(target, "AUDITOR", port, profile, request, catalog)
            raw_review = decode_json(response.get("text"))
            atomic_json(target / "REVIEW_WIRE.json", raw_review)
            review = compile_semantic_review(raw_review, control["view"])
            atomic_json(target / "REVIEW.json", review)
            row = score_control(control, review)
            usage.append(response.get("usage") or {})
            from ioabench.models import ModelResponse
            costs.append(usage_cost(ModelResponse(text="", model_id=model_id, usage=response.get("usage") or {}), entry))
        except Exception as exc:
            row = {"id": control["id"], "expected": control["expected"], "verdict": None,
                   "correct": False, "error_type": type(exc).__name__, "error": str(exc)}
            rows.append(row)
            atomic_json(directory / "CONTROL_PROGRESS.json", {"rows": rows, "status": "DIAGNOSIS_REQUIRED"})
            # A missing response or a Provider error is not a judgment and must be diagnosed first.
            return {"passed": False, "status": "DIAGNOSIS_REQUIRED", "rows": rows}
        rows.append(row)
        atomic_json(directory / "CONTROL_PROGRESS.json", {"rows": rows, "status": "IN_PROGRESS"})
    if source_tree_hash(ROOT) != runtime_hash:
        raise ValueError("runtime changed during reviewer controls; original responses retained")
    report = {**summarize_controls(rows), "rows": rows, "auditor": model_id,
              "usage": {key: sum(int(item.get(key) or 0) for item in usage)
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
              "monetary_cost": {"status": "ESTIMATED", "currency": "USD", "amount": sum(item.get("amount") or 0 for item in costs)},
              "source_control_sha256": contract["controls_sha256"]}
    report["status"] = "ENGINEERING_CONTROLS_PASS" if report["passed"] else "CONTROLS_FAILED_EXPANSION_BLOCKED"
    report["evidence_sha256"] = {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*") if path.is_file() and path.name != "CONTROL_RESULT.json"}
    atomic_json(result_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--auditor", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    safe_id(args.run_id)
    directory = ROOT / "artifacts/v5/data_factory/quality_controls" / args.run_id
    with _lock(ROOT / "artifacts/v5/overnight_runs/.writer.lock"):
        directory.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(audit(directory, args.auditor, args.prepare_only, preflight=args.preflight))
    print(__import__("json").dumps({key: report.get(key) for key in (
        "status", "gold_count", "correct", "false_accepts", "false_rejects", "abstains", "unsupported_evidence", "usage", "monetary_cost")}, ensure_ascii=False))
    return 0 if report.get("passed") or args.prepare_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
