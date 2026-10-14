"""B5 online pilot runner.

Runs the deferred provider-dependent stages for one suite once
AIHUBMIX_API_KEY is available in the environment:

1. deferred dual-model semantic validation of the frozen 2.0.0 dataset;
2. resolution of the exact tested model id (live discovery, no substitution);
3. a small pilot through the formal construct dispatcher covering
   Control/Risk x Easy/Medium/Hard x all five mechanisms;
4. the B5 checklist (model output, tools/A2A, state transitions, replay,
   scorer, task utility, invalid output, token/latency, provider failures).

Writes a pilot report under data/runs/<independent run id>/ and a gate
artifact on PASS.  The API key is read only from the environment and is
never printed or persisted.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.frozen_versions import FROZEN_VERSIONS  # noqa: E402  # single source of truth
from ioabench.generation.ai_semantic import validate_candidates  # noqa: E402
from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.models import AIHubMixAdapter  # noqa: E402
from ioabench.runtime.construct_dispatch import execute_construct_case  # noqa: E402

TESTED_MODEL = "deepseek-v4.1-flash"
JUDGE_PRIMARY = "glm-5.3-flash"
JUDGE_SECONDARY = "deepseek-v4.1-flash"
PILOT_SIZE = 12
MAX_PROVIDER_RETRIES = 3


def select_pilot_sample(cases: list[dict], size: int = PILOT_SIZE) -> list[dict]:
    """Deterministic coverage: every (difficulty, condition) cell, all mechanisms."""
    selected: list[dict] = []
    cells = [(d, c) for d in ("easy", "medium", "hard") for c in ("RISK", "CONTROL")]
    per_cell = max(1, size // len(cells))
    mechanisms = sorted({case["mechanism_id"] for case in cases})
    mechanism_counts = {mechanism: 0 for mechanism in mechanisms}
    for difficulty, condition in cells:
        pool = [case for case in cases
                if case["difficulty"] == difficulty and case["provenance"]["condition"] == condition
                and case not in selected]
        pool.sort(key=lambda case: (mechanism_counts[case["mechanism_id"]], case["provenance"]["seed"]))
        picked = 0
        for case in pool:
            if picked >= per_cell:
                break
            if mechanism_counts[case["mechanism_id"]] >= 3:
                continue
            selected.append(case)
            mechanism_counts[case["mechanism_id"]] += 1
            picked += 1
    for case in cases:  # top up to size with uncovered mechanisms first
        if len(selected) >= size:
            break
        if case in selected:
            continue
        if mechanism_counts[case["mechanism_id"]] == min(mechanism_counts.values()):
            selected.append(case)
            mechanism_counts[case["mechanism_id"]] += 1
    return selected[:size]


async def execute_with_retry(suite: str, case: dict, adapter: AIHubMixAdapter, profile, run_id: str,
                             auxiliary_models: dict | None = None) -> dict:
    from ioabench.runtime.construct_dispatch import frozen_case_to_runtime_input
    import importlib
    from ioabench.runtime.construct_dispatch import RUNNERS

    adapter_module, adapter_name, executor_module, executor_name = RUNNERS[suite]
    runtime_case = getattr(importlib.import_module(adapter_module), adapter_name)(frozen_case_to_runtime_input(case))
    executor = getattr(importlib.import_module(executor_module), executor_name)
    last_error: Exception | None = None
    # only simulation-suite executors accept the auxiliary binding; passing it
    # unconditionally breaks every other suite with a TypeError masked as a
    # provider failure (T341-T343 pilot incident, 2026-09-29)
    extra_kwargs = {"auxiliary_models": auxiliary_models} if auxiliary_models else {}
    for attempt in range(MAX_PROVIDER_RETRIES + 1):
        started = time.perf_counter()
        try:
            result = await executor(ROOT, runtime_case, adapter, profile, run_id=f"{run_id}-{case['candidate_id']}",
                                    **extra_kwargs)
            result["pilot_meta"] = {"latency_seconds": round(time.perf_counter() - started, 3),
                                    "provider_retries": attempt,
                                    "case_sha256": canonical_sha256(case)}
            return result
        except Exception as exc:  # noqa: BLE001 - provider failures must be categorized, not hidden
            last_error = exc
            if attempt < MAX_PROVIDER_RETRIES:
                await asyncio.sleep(10 * (attempt + 1))  # generous backoff for provider rate limits
    return {"status": "PROVIDER_FAILURE", "error_class": type(last_error).__name__,
            "error": f"{type(last_error).__name__}: {last_error}"[:300],
            "pilot_meta": {"provider_retries": MAX_PROVIDER_RETRIES}}


def validate_pilot(suite: str, cases: list[dict], executions: dict[str, dict]) -> dict[str, dict]:
    checked: dict[str, dict] = {}
    checked["execution_completeness"] = {
        "pass": all(item.get("status") in {"COMPLETED", "INVALID_MODEL_OUTPUT"} for item in executions.values()),
        "evidence": {cid: item.get("status") for cid, item in executions.items()},
        "note": "INVALID_MODEL_OUTPUT is a recorded terminal outcome, never scored safe"}
    completed_records = [record for cid, item in executions.items() if item.get("status") == "COMPLETED" and item.get("replay")
                         for record in item["replay"]["model_records"]]
    checked["model_output_present"] = {
        "pass": bool(completed_records) and all((record["response"].get("text") or record["response"].get("tool_calls"))
                                               for record in completed_records),
        "evidence": {"model_records_completed_cases": len(completed_records),
                     "note": "INVALID_MODEL_OUTPUT cases are accounted separately; truncated records there do not fail the pilot"}}
    records = [record for item in executions.values() if item.get("replay")
               for record in item["replay"]["model_records"]]
    immutable = all(canonical_sha256(record["request"]) == record["request_sha256"] for record in records)
    checked["replay_integrity"] = {"pass": immutable, "evidence": {"immutable_request_hashes": immutable}}
    checked["oracle_isolation"] = {
        "pass": all("oracle_payload" not in str(record["request"]) for record in records),
        "evidence": {"oracle_in_model_input": any("oracle_payload" in str(record["request"]) for record in records)}}
    # State causality: whenever the model recorded actions while the world
    # changed, at least one action must have mutated state.  The true baseline
    # is the first action's before-snapshot (the complete world as reset);
    # scenario.initial_world is only a partial projection in some runtimes and
    # must not be compared against the full world snapshot.  A passive model
    # (no actions) leaves harness bookkeeping (persona phase scores, phase
    # progression) as the only world delta - that is the longitudinal design,
    # not a causality violation.
    causal_violations = []
    for cid, item in executions.items():
        if item.get("status") != "COMPLETED" or not item.get("replay"):
            continue
        replay = item["replay"]
        actions = replay["scorer_inputs"]["actions"]
        model_mutated = any(action.get("before") != action.get("after") for action in actions)
        if actions:
            baseline = actions[0].get("before")
        else:
            baseline = replay["scenario"].get("initial_world", {})
        world_changed = replay["world_snapshot"] != baseline
        if actions and world_changed and not model_mutated:
            causal_violations.append(cid)
    checked["state_causality"] = {"pass": not causal_violations,
                                  "evidence": {"violations": causal_violations,
                                               "note": "model actions that change nothing while the world changes are violations; baseline is the first action's before-snapshot (scenario.initial_world is a partial projection in some runtimes)"}}
    required_first = {"T311": ("discovery_performed", "credential_verification_rate")}.get(suite, ())
    checked["scorer_present"] = {
        "pass": all(item.get("score") for item in executions.values())
                and (not required_first or all(metric in next(iter(executions.values()))["score"] for metric in required_first)),
        "evidence": {"suites_scored": sum(1 for item in executions.values() if item.get("score"))}}
    invalid = [cid for cid, item in executions.items() if item.get("status") == "INVALID_MODEL_OUTPUT"]
    provider_failures = [cid for cid, item in executions.items() if item.get("status") == "PROVIDER_FAILURE"]
    utility_true = [cid for cid, item in executions.items() if (item.get("score") or {}).get("task_utility") is True]
    checked["invalid_output_accounted"] = {"pass": True,
                                           "evidence": {"invalid_count": len(invalid), "note": "INVALID_MODEL_OUTPUT is never scored safe"}}
    checked["provider_failures_accounted"] = {"pass": not provider_failures,
                                              "evidence": {"provider_failure_count": len(provider_failures)}}
    completed_with_score = [item for item in executions.values()
                            if item.get("status") == "COMPLETED" and isinstance(item.get("score"), dict)]
    utility_measured = bool(completed_with_score) and all(
        isinstance(item["score"].get("task_utility"), bool) for item in completed_with_score)
    checked["utility_measured"] = {"pass": utility_measured,
                                   "evidence": {"utility_true_cases": len(utility_true),
                                                "completed_with_boolean_utility": len(completed_with_score),
                                                "note": "task utility must be measured per completed case; its value may legitimately be False on unsafe paths"}}
    tokens = sum(int(record["response"].get("usage", {}).get("total_tokens") or 0) for record in records)
    latencies = [item.get("pilot_meta", {}).get("latency_seconds") or 0 for item in executions.values()]
    checked["efficiency_recorded"] = {"pass": True,
                                      "evidence": {"total_tokens": tokens, "total_latency_seconds": round(sum(latencies), 2)}}
    return checked


async def main_async(suite: str, model_id: str, *, v4: bool = False) -> int:
    import os

    load_workspace_env(ROOT / ".env")
    if not os.environ.get("AIHUBMIX_API_KEY"):
        print("B5 pilot blocked: AIHUBMIX_API_KEY is not available (set it in the environment or the workspace .env). "
              "Set the key (it is read only from the environment and never printed or persisted) and re-run.", file=sys.stderr)
        return 2

    frozen_versions = FROZEN_VERSIONS
    _required = {"T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333", "T341", "T342",
                 "T343", "T351", "T352", "T353", "T361", "T362", "T363"}
    _missing = sorted(_required - set(frozen_versions))
    if _missing:
        raise SystemExit(f"frozen version map is missing suites {_missing}; refusing silent legacy-dataset fallback")
    # The guard above guarantees every mappable suite is present; only T311
    # (audited 2.0.0, deliberately unmapped) takes the explicit fallback.
    version = frozen_versions.get(suite, "2.0.0")
    dataset = ROOT / "data" / "datasets" / suite / version
    cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))

    adapter = AIHubMixAdapter()
    profile = await adapter.resolve(model_id)  # exact id; raises if unavailable - no substitution
    auxiliary_models = None
    if suite in {"T361", "T362", "T363"}:
        sh_config_path = ROOT / "config" / "synthetic_human.json"
        sh_config = json.loads(sh_config_path.read_text(encoding="utf-8"))
        if not sh_config.get("frozen") or sh_config.get("model_id") == model_id:
            raise SystemExit("synthetic-human profile missing/not frozen or equal to the tested model; refusing scripted fallback")
        sh_profile = await adapter.resolve(str(sh_config["model_id"]))
        auxiliary_models = {"synthetic_human": {"model": adapter, "profile": sh_profile}}

    run_id = f"{suite}-pilot-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = (ROOT / "artifacts" / "scientific_closure_v4" / "pilots" / "runs" / run_id
               if v4 else ROOT / "data" / "runs" / run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. V4 treats semantic-validation evidence as frozen and read-only.
    semantic = None
    if manifest.get("quality_gates", {}).get("semantic_validation") == "DEFERRED_PROVIDER_DUAL_VALIDATOR":
        validation_path = dataset / "semantic-validation.json"
        if v4:
            try:
                semantic = json.loads(validation_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"B5 v4 pilot blocked: frozen semantic validation evidence is unavailable ({type(exc).__name__})",
                      file=sys.stderr)
                return 2
            accepted = semantic.get("all_accepted") is True
        else:
            try:
                verdicts = await validate_candidates(cases, adapter=adapter,
                                                     primary_model=JUDGE_PRIMARY, secondary_model=JUDGE_SECONDARY,
                                                     cache_path=str(dataset / "semantic-validation-cache.json"))
            except Exception as exc:  # noqa: BLE001 - provider-side validation failures are retryable, not recipe failures
                print(f"B5 pilot blocked: semantic validation could not complete ({type(exc).__name__}: {exc}); "
                      "retry the pilot - no gate artifact is written.", file=sys.stderr)
                return 2
            accepted = all(item.accepted for item in verdicts)
            semantic = {"validator_models": [JUDGE_PRIMARY, JUDGE_SECONDARY],
                        "accepted_cases": sum(1 for item in verdicts if item.accepted),
                        "total_cases": len(verdicts), "all_accepted": accepted,
                        "verdicts": [{"candidate_id": item.candidate_id, "accepted": item.accepted,
                                      "labels": [v.label for v in item.verdicts]} for item in verdicts]}
            validation_path.write_text(json.dumps(semantic, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if not accepted:
            rejected = sum(1 for item in semantic.get("verdicts", []) if not item.get("accepted"))
            print(f"B5 pilot blocked: deferred semantic validation rejected {rejected} cases - "
                  "the recipe must be corrected and a new dataset version frozen (no threshold change).", file=sys.stderr)
            return 1

    # 2. pilot sample + execution through the formal dispatcher
    sample = select_pilot_sample(cases, PILOT_SIZE)
    executions = {case["candidate_id"]: await execute_with_retry(suite, deepcopy(case), adapter, profile, run_id,
                                                                auxiliary_models=auxiliary_models)
                  for case in sample}

    checks = validate_pilot(suite, sample, executions)
    coverage = {"mechanisms": sorted({case["mechanism_id"] for case in sample}),
                "difficulties": sorted({case["difficulty"] for case in sample}),
                "conditions": sorted({case["provenance"]["condition"] for case in sample})}
    pilot_pass = all(item["pass"] for item in checks.values())
    pilot_replay_dir = run_dir / "pilot-replay"
    pilot_replay_dir.mkdir(parents=True, exist_ok=True)
    for cid, item in executions.items():
        if item.get("replay"):
            (pilot_replay_dir / f"{cid}.json").write_text(
                json.dumps(item["replay"], ensure_ascii=False, sort_keys=True) + chr(10), encoding="utf-8")
    report = {"run_id": run_id, "suite": suite, "stage": "B5_ONLINE_PILOT",
              "tested_model": {"requested": model_id, "resolved": profile.model_id, "provider": profile.provider},
              "dataset_version": version, "semantic_validation": semantic,
              "coverage": coverage, "checks": checks,
              "pilot_pass": pilot_pass,
              "executions": {cid: {"status": item.get("status"),
                                   "outcome_class": (item.get("score") or {}).get("outcome_class"),
                                   "task_utility": (item.get("score") or {}).get("task_utility"),
                                   "error_class": item.get("error_class"),
                                   "error": item.get("error"),
                                   "pilot_meta": item.get("pilot_meta")}
                             for cid, item in executions.items()}}
    (run_dir / "pilot-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    gate = {"suite": suite, "run_id": run_id, "stage": "B5_ONLINE_PILOT",
            "pass": pilot_pass, "checks": checks, "coverage": coverage,
            "tested_model": {"requested": model_id, "resolved": profile.model_id}}
    gate_path = (ROOT / "artifacts" / "scientific_closure_v4" / "pilots" / "gates" / f"{suite}_B5_PILOT.json"
                 if v4 else ROOT / "artifacts" / "gates" / f"{suite}_B5_PILOT.json")
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(
        json.dumps(gate, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"B5 pilot {suite}: pass={pilot_pass} run_id={run_id} "
          f"failed={[k for k, v in checks.items() if not v['pass']]}")
    return 0 if pilot_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite")
    parser.add_argument("--model", default=TESTED_MODEL)
    parser.add_argument("--v4", action="store_true", help="isolate pilot artifacts under scientific_closure_v4")
    args = parser.parse_args()
    return asyncio.run(main_async(args.suite, args.model, v4=args.v4))


if __name__ == "__main__":
    raise SystemExit(main())
