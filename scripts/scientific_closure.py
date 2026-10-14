"""Offline v3.2 evidence checks. Never executes a provider or rewrites old evidence."""
from __future__ import annotations

import argparse
import ast
import asyncio
from collections import Counter, defaultdict, deque
from dataclasses import asdict, fields
from datetime import datetime, timezone
import hashlib
import difflib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import re
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = ROOT / "archive/deliveries"
sys.path.insert(0, str(ROOT / "src"))

from ioabench.frozen_versions import FROZEN_VERSIONS
from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.models import ModelProfile, ModelResponse

BASELINE = ROOT / "artifacts/scientific_closure_v3_2/baseline.json"
RELEASE = ROOT / "release/BENCHMARK_RELEASE_v3-20260930.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def baseline_path(name: str) -> Path:
    path = ROOT / name
    # Frozen baseline names remain unchanged after the documented layout migration.
    if not path.exists() and Path(name).name == name and name.endswith(".zip"):
        return ARCHIVE_DIR / name
    return path


def write_new(path: Path, value) -> None:
    """Refuse to overwrite an earlier audit, including failed audit evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def reference(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}


def baseline() -> dict:
    if BASELINE.exists():
        return verify_baseline()
    roots = ("src", "contracts", "config", "data", "artifacts", "release")
    files = {}
    for name in roots:
        for path in sorted((ROOT / name).rglob("*")):
            if not path.is_file() or any(part in {"__pycache__", ".pytest_cache", "scientific_closure_v3_2"} for part in path.parts):
                continue
            if path.name.startswith(".env") or path.suffix in {".pyc", ".pyo"}:
                continue
            files[path.relative_to(ROOT).as_posix()] = sha256(path)
    for path in sorted(ARCHIVE_DIR.glob("*.zip")):
        files[path.relative_to(ROOT).as_posix()] = sha256(path)
    backups = BASELINE.parent / "state_before"
    backups.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / "state").glob("*")):
        if path.is_file():
            shutil.copy2(path, backups / path.name)
    value = {"artifact": "SCIENTIFIC_CLOSURE_BASELINE", "version": "3.2.0",
             "captured_at_utc": datetime.now(timezone.utc).isoformat(),
             "source_tree_sha256": source_tree_hash(ROOT), "base_release": reference(RELEASE),
             "files": files, "state_backups": [reference(p) for p in sorted(backups.glob("*"))]}
    write_new(BASELINE, value)
    return {"protected_files": len(files), "baseline": reference(BASELINE), "pass": True}


def verify_baseline() -> dict:
    old = read_json(BASELINE)
    failures = [name for name, digest in old["files"].items()
                if not baseline_path(name).is_file() or sha256(baseline_path(name)) != digest]
    return {"protected_files": len(old["files"]), "changed_or_missing": failures, "pass": not failures}


def verify_dataset(manifest: dict, cases: list, run: dict, release: dict, suite: str, version: str) -> dict:
    content = canonical_sha256({"manifest": {**manifest, "content_sha256": None}, "cases": cases})
    ids = [case["candidate_id"] for case in cases]
    checks = {
        "content_recomputed": content == manifest["content_sha256"],
        "run_hash_match": content == run["benchmark"]["dataset_hashes"][suite],
        "release_hash_match": content == release["datasets"][suite]["content_sha256"],
        "versions_match": manifest["version"] == run["benchmark"]["dataset_versions"][suite] == release["datasets"][suite]["version"] == version,
        "frozen": manifest["status"] == "FROZEN",
        "90_unique_cases": len(ids) == len(set(ids)) == 90,
        "difficulty_30_each": Counter(c["difficulty"] for c in cases) == {"easy": 30, "medium": 30, "hard": 30},
        "conditions_45_each": Counter(c["provenance"]["condition"] for c in cases) == {"CONTROL": 45, "RISK": 45},
    }
    return {"checks": checks, "content_sha256": content, "pass": all(checks.values())}


def inventory() -> dict:
    release = read_json(RELEASE)
    rows = []
    for suite, version in FROZEN_VERSIONS.items():
        run_id = f"deepseek-v4.1-flash-{suite}-{version}-formal"
        run_dir = ROOT / "data/runs" / run_id
        ds_dir = ROOT / "data/datasets" / suite / version
        run_path = run_dir / "manifest" / f"{run_id}.json"
        run = read_json(run_path)
        manifest = read_json(ds_dir / "manifest.json")
        cases = [json.loads(line) for line in (ds_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        dataset = verify_dataset(manifest, cases, run, release, suite, version)
        cases_by_id = {c["candidate_id"]: c for c in cases}
        results = read_json(run_dir / "results.json")
        checks = {"run_manifest_hash": run["manifest_sha256"] == canonical_sha256({k: v for k, v in run.items() if k != "manifest_sha256"}),
                  "exact_run_id": run["run_id"] == run_id,
                  "tested_model": run["tested_model"]["model_id"] == "deepseek-v4.1-flash",
                  "90_terminal": len(results) == 90 and all(v["status"] in {"COMPLETED", "INVALID_MODEL_OUTPUT"} for v in results.values()),
                  "exact_case_coverage": Counter(v["dispatch"]["case_id"] for v in results.values()) == Counter(cases_by_id.keys())}
        failures, roles = [], {}
        params, finishes, response_models, source_hashes = Counter(), Counter(), Counter(), Counter()
        max_completion, records_count, missing_usage = 0, 0, 0
        for unit_id, value in results.items():
            replay = value.get("replay")
            if not replay:
                failures.append({"unit": unit_id, "check": "missing_replay"})
                continue
            case_id = value["dispatch"]["case_id"]
            if canonical_sha256(cases_by_id[case_id]) != value["dispatch"]["case_sha256"]:
                failures.append({"unit": unit_id, "check": "frozen_case_hash"})
            if replay["content_sha256"] != canonical_sha256({k: v for k, v in replay.items() if k != "content_sha256"}):
                failures.append({"unit": unit_id, "check": "bundle_hash"})
            source_hashes[replay["scenario"]["manifest"]["source_tree_sha256"]] += 1
            for index, record in enumerate(replay["model_records"]):
                records_count += 1
                request, response = record["request"], record["response"]
                if canonical_sha256(request) != record["request_sha256"]:
                    failures.append({"unit": unit_id, "record": index, "check": "request_hash"})
                role = request.get("role_metadata", {}).get("role", "UNKNOWN")
                group = roles.setdefault(role, {"system_prompt_hashes": set(), "initial_task_hashes": set(), "tool_schema_hashes": set()})
                group["system_prompt_hashes"].add(canonical_sha256([m for m in request["messages"] if m["role"] == "system"]))
                group["initial_task_hashes"].add(canonical_sha256(next((m for m in request["messages"] if m["role"] == "user"), None)))
                group["tool_schema_hashes"].add(canonical_sha256(request["tools"]))
                if role != "SYNTHETIC_HUMAN":
                    response_models[response.get("model_id", "MISSING")] += 1
                    params[json.dumps(request["parameters"], sort_keys=True)] += 1
                    finishes[str(response.get("finish_reason"))] += 1
                    completion = response.get("usage", {}).get("completion_tokens")
                    if isinstance(completion, int):
                        max_completion = max(max_completion, completion)
                    else:
                        missing_usage += 1
        checks["replay_and_case_hashes"] = not failures
        checks["response_model_identity"] = set(response_models) == {"deepseek-v4.1-flash"}
        rows.append({"suite": suite, "dataset_version": version, "run_id": run_id,
                     "dataset_binding": dataset, "identity_checks": checks,
                     "result_statuses": dict(Counter(v["status"] for v in results.values())),
                     "outcomes": dict(Counter(v["score"]["outcome_class"] for v in results.values())),
                     "run_source_sha256": run["runtime"]["git_sha"].removeprefix("sha256:"),
                     "case_source_hashes": dict(source_hashes), "model_records": records_count,
                     "tested_response_models": dict(response_models), "tested_parameters": dict(params),
                     "finish_reasons": dict(finishes), "maximum_completion_tokens": max_completion,
                     "records_missing_completion_usage": missing_usage,
                     "prompt_tool_inventory": {k: {field: sorted(vals) for field, vals in v.items()} for k, v in roles.items()},
                     "failures": failures, "evidence": [reference(run_path), reference(run_dir / "results.json"), reference(ds_dir / "manifest.json"), reference(ds_dir / "cases.jsonl")],
                     "pass": dataset["pass"] and all(checks.values())})
        print(f"{suite}: dataset={dataset['pass']} identity={all(checks.values())} records={records_count}", flush=True)
    return {"artifact": "V32_S0_EVIDENCE_INVENTORY", "version": "3.2.0", "base_release": reference(RELEASE),
            "current_source_sha256": source_tree_hash(ROOT), "release_source_sha256": release["source_tree_sha256"],
            "suites": rows, "pass": all(row["pass"] for row in rows),
            "limits": ["Identity and content checks do not establish canonical status.", "Source compatibility, deep isolation and score recomputation remain separate obligations."]}


class MissingRecordedRequest(RuntimeError):
    pass


class RecordedResponses:
    """Consume exact recorded requests, preserving repeated-call response order."""

    def __init__(self, records: list, *, t311_cap_diagnostic: bool = False):
        self.pending = defaultdict(deque)
        self.expected_requests = {}
        self.consumed = 0
        self.cap_diagnostic = t311_cap_diagnostic
        for record in records:
            request = record["request"]
            key = canonical_sha256(request)
            self.pending[key].append(record["response"])
            self.expected_requests[key] = request

    def __deepcopy__(self, memo):
        # All calls share consumption accounting; no unseen response is invented.
        return self

    async def generate(self, profile, request):
        value = asdict(request)
        if self.cap_diagnostic and value["parameters"] == {"temperature": 0.0, "max_tokens": 8192}:
            value["parameters"] = {"temperature": 0.0, "max_tokens": 4096}
        key = canonical_sha256(value)
        if not self.pending[key]:
            candidates = [(expected, k) for k, expected in self.expected_requests.items()
                          if self.pending[k] and expected.get("role_metadata") == value.get("role_metadata")]
            differing = sorted(k for k in value if not candidates or canonical_sha256(value[k]) != canonical_sha256(candidates[0][0].get(k)))
            raise MissingRecordedRequest(json.dumps({"request_sha256": key, "differing_fields_vs_next_role_record": differing,
                                                     "consumed": self.consumed}, sort_keys=True))
        response = self.pending[key].popleft()
        if response["model_id"] != profile.model_id:
            raise MissingRecordedRequest("profile model ID differs from recorded response")
        self.consumed += 1
        accepted = {field.name for field in fields(ModelResponse)}
        return ModelResponse(**{k: v for k, v in response.items() if k in accepted})


def trace_replay(suite_filter: str, limit: int, cap_diagnostic: bool, t353_main_only: bool = False, source_hash_filter: str | None = None) -> dict:
    from ioabench.runtime.construct_dispatch import execute_construct_case, SIMULATION_SUITES, frozen_case_to_runtime_input

    reports = []
    selected = FROZEN_VERSIONS if suite_filter == "all" else {suite_filter: FROZEN_VERSIONS[suite_filter]}
    profile = ModelProfile("replay", "deepseek-v4.1-flash", {}, {})

    def forbidden_network(*args, **kwargs):
        raise RuntimeError("NETWORK_FORBIDDEN_IN_OFFLINE_CLOSURE_AUDIT")

    # Windows creates the event loop's local socketpair before the network guard.
    with asyncio.Runner() as runner, patch("socket.socket.connect", forbidden_network), patch("socket.socket.connect_ex", forbidden_network), patch("socket.create_connection", forbidden_network):
        for suite, version in selected.items():
            run_id = f"deepseek-v4.1-flash-{suite}-{version}-formal"
            run_dir = ROOT / "data/runs" / run_id
            cases = {c["candidate_id"]: c for c in (json.loads(line) for line in (ROOT / "data/datasets" / suite / version / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
            results = read_json(run_dir / "results.json")
            units = []
            for unit_id, previous in list(results.items())[:limit or None]:
                replay = previous["replay"]
                if source_hash_filter and replay["scenario"]["manifest"]["source_tree_sha256"] != source_hash_filter:
                    continue
                model = RecordedResponses(replay["model_records"], t311_cap_diagnostic=cap_diagnostic and suite == "T311")
                auxiliary = None
                if suite in SIMULATION_SUITES:
                    auxiliary = {"synthetic_human": (model, ModelProfile("replay", "glm-5.3-flash", {}, {}, "SYNTHETIC_HUMAN"))}
                row = {"unit_id": unit_id, "case_id": previous["dispatch"]["case_id"], "cap_diagnostic": model.cap_diagnostic}
                try:
                    if suite == "T353" and t353_main_only:
                        from ioabench.runtime.discovery_selection import build_discovery_case_from_skeleton, execute_discovery_selection
                        runtime_case = build_discovery_case_from_skeleton(frozen_case_to_runtime_input(cases[row["case_id"]]))
                        current = runner.run(execute_discovery_selection(ROOT, runtime_case, model, profile, run_id=replay["run_id"], _paired=False))
                    else:
                        optional = {"auxiliary_models": auxiliary} if auxiliary is not None else {}
                        current = runner.run(execute_construct_case(ROOT, suite, cases[row["case_id"]], model, profile,
                                                                    run_id=replay["run_id"], **optional))
                    excluded = {"counterfactual_selection_delta"} if suite == "T353" and t353_main_only else set()
                    checks = {"status": current["status"] == previous["status"],
                              "score": {k: v for k, v in current["score"].items() if k not in excluded} == {k: v for k, v in previous["score"].items() if k not in excluded},
                              "actions": current["replay"]["scorer_inputs"]["actions"] == replay["scorer_inputs"]["actions"],
                              "world": current["replay"]["world_snapshot"] == replay["world_snapshot"],
                              "all_recorded_calls_consumed": model.consumed == len(replay["model_records"])}
                    row.update({"checks": checks, "pass": all(checks.values()),
                                "excluded_score_fields": sorted(excluded),
                                "changed_score_fields": sorted(k for k in set(current["score"]) | set(previous["score"]) if current["score"].get(k) != previous["score"].get(k))})
                except Exception as exc:
                    # Only known hash-only diagnostics are printed; arbitrary provider text is never copied.
                    row.update({"pass": False, "error_class": type(exc).__name__,
                                "detail": str(exc) if isinstance(exc, MissingRecordedRequest) else "see offline execution path", "consumed": model.consumed})
                units.append(row)
            report = {"suite": suite, "units": units, "pass": bool(units) and all(r["pass"] for r in units)}
            reports.append(report)
            print(f"{suite}: {sum(r['pass'] for r in units)}/{len(units)} trace checks passed", flush=True)
    return {"artifact": "OFFLINE_RECORDED_RESPONSE_REEXECUTION", "version": "3.2.0", "source_sha256": source_tree_hash(ROOT),
            "t353_main_only_diagnostic": t353_main_only,
            "recorded_source_hash_filter": source_hash_filter,
            "provider_calls": 0, "network_forbidden": True, "suites": reports, "pass": all(r["pass"] for r in reports),
            "limits": ["A matched finite trajectory does not establish unobserved paths or provider counterfactuals.", "T311 cap normalization, if requested, is diagnostic only and cannot establish sampling-profile equivalence."]}


def reproduce_invalid_resume() -> dict:
    from ioabench.runtime.batch import BatchRunner
    from ioabench.runtime.scheduler import WorkUnit
    statuses = ("COMPLETED", "INVALID_MODEL_OUTPUT", "RETRYABLE_INFRA_FAILURE")
    with tempfile.TemporaryDirectory(prefix="ioa-closure-resume-") as directory:
        state_path = Path(directory) / "checkpoint.json"
        write_new(state_path, {s: {"status": s} for s in statuses})
        units = tuple(WorkUnit(s, "offline-recorded", "T323", "2.4.0", s, "RISK", 1) for s in statuses)
        executed = []

        def executor(unit):
            executed.append(unit.work_id)
            return {"status": "COMPLETED"}

        result = BatchRunner(state_path).run(units, executor, resume=True)
        return {"input_statuses": list(statuses), "executed": executed,
                "after_statuses": {s: result[s]["status"] for s in statuses},
                "frozen_policy_satisfied": "INVALID_MODEL_OUTPUT" not in executed,
                "completed_result_preserved": "COMPLETED" not in executed,
                "provider_calls": 0}


def historical_status_observations(export: Path) -> dict:
    """Extract only aggregate tool output; never copy the secret-bearing conversation."""
    history = read_json(export)
    rows = []
    pattern = re.compile(r"^(T3\d{2}) (?:formal:|formal results:|results:)\s*90(?:\s+units)?\s*(\{[^{}]+\})\s*$")
    for message in history["messages"]:
        for wrapper in message.get("parts", []):
            part = wrapper["part"]
            if part.get("type") != "tool":
                continue
            state = part.get("state", {})
            command = state.get("input", {}).get("command", "")
            output = state.get("output", "")
            if not isinstance(output, str):
                continue
            for line in output.splitlines():
                match = pattern.fullmatch(line.strip())
                if not match:
                    continue
                suite = match[1]
                if suite not in FROZEN_VERSIONS:
                    continue
                version = FROZEN_VERSIONS[suite]
                run_id = f"deepseek-v4.1-flash-{suite}-{version}-formal"
                # Accept only explicit path or an explicit suite/version tuple in the tool input.
                if run_id not in command and not re.search(r'["\']' + suite + r'["\']\s*,\s*["\']' + re.escape(version) + r'["\']', command):
                    continue
                counts = ast.literal_eval(match[2])
                if sum(counts.values()) != 90 or not all(isinstance(v, int) for v in counts.values()):
                    continue
                rows.append({"suite": suite, "run_id": run_id, "part_id": wrapper["id"],
                             "message_id": message["id"], "message_time_unix_ms": message["time_created"],
                             "tool_time": state.get("time", {}), "counts": counts, "quoted_output_line": line.strip(),
                             "tool_input_sha256": canonical_sha256(state.get("input", {}))})
    changed = []
    for suite, version in FROZEN_VERSIONS.items():
        observed = [r for r in rows if r["suite"] == suite]
        if not observed:
            continue
        highest = max(observed, key=lambda r: r["counts"].get("INVALID_MODEL_OUTPUT", 0))
        results_path = ROOT / "data/runs" / highest["run_id"] / "results.json"
        final = Counter(v["status"] for v in read_json(results_path).values())
        decrease = highest["counts"].get("INVALID_MODEL_OUTPUT", 0) - final.get("INVALID_MODEL_OUTPUT", 0)
        if decrease > 0:
            changed.append({"suite": suite, "run_id": highest["run_id"], "earlier_counts": highest["counts"],
                            "earlier_part_id": highest["part_id"], "final_counts": dict(final),
                            "minimum_previously_invalid_no_longer_invalid": decrease,
                            "exact_earlier_case_ids": "UNKNOWN_AGGREGATE_ONLY", "final_evidence": reference(results_path)})
    return {"external_export_path": str(export), "external_export_sha256": sha256(export),
            "source_type": "exported_historical_tool_results_not_assistant_conclusions",
            "observations": rows, "confirmed_invalid_count_decreases": changed,
            "limits": ["Aggregate observations prove count changes but cannot recover the original case-level outputs.",
                       "Suites absent from this list are not thereby proven free of earlier invalid retries."]}


def policy_impact(export: Path) -> dict:
    retry = reproduce_invalid_resume()
    observations = historical_status_observations(export)
    run_dir = ROOT / "data/runs/deepseek-v4.1-flash-T353-2.3.0-formal"
    results = read_json(run_dir / "results.json")
    pairs = []
    for unit, result in results.items():
        branches = result["replay"]["scenario"].get("paired_runs", {})
        pairs.append({"unit_id": unit, "case_id": result["dispatch"]["case_id"],
                      "branch_fields": {mode: sorted(value) for mode, value in branches.items()},
                      "both_branch_raw_replays_retained": all("replay" in branches.get(mode, {}) for mode in ("honest", "manipulated")),
                      "paired_selection_used_by_scorer": result["replay"]["scorer_inputs"].get("paired_selection") is not None,
                      "paired_selection": result["replay"]["scorer_inputs"].get("paired_selection"),
                      "recorded_counterfactual_selection_delta": result["score"]["counterfactual_selection_delta"],
                      "difference_of_recorded_pair_selections": float(branches["honest"]["selected_agent_id"] != branches["manipulated"]["selected_agent_id"])})
    snapshots = []
    batch_path = ROOT / "src/ioabench/runtime/batch.py"
    for archive_path in sorted(ARCHIVE_DIR.glob("*.zip")):
        with ZipFile(archive_path) as archive:
            entry = "src/ioabench/runtime/batch.py"
            if entry in archive.namelist():
                snapshots.append({"archive": reference(archive_path), "entry": entry,
                                  "batch_sha256": hashlib.sha256(archive.read(entry)).hexdigest(),
                                  "same_as_current_batch": hashlib.sha256(archive.read(entry)).hexdigest() == sha256(batch_path)})
    return {"artifact": "SCIENTIFIC_CLOSURE_POLICY_IMPACT", "version": "3.2.0", "provider_calls": 0,
            "retry_policy_reproduction": retry, "historical_observations": observations,
            "t353_pair_replay": {"run_id": run_dir.name, "cases": pairs,
                                 "raw_pair_replays_missing": sum(not p["both_branch_raw_replays_retained"] for p in pairs),
                                 "pair_delta_mismatches": [p["unit_id"] for p in pairs if p["recorded_counterfactual_selection_delta"] != p["difference_of_recorded_pair_selections"]],
                                 "source": reference(ROOT / "src/ioabench/runtime/discovery_selection.py"),
                                 "source_lines": "319-340: only selected_agent_id/task_utility/outcome_class retained from each paired result",
                                 "results": reference(run_dir / "results.json"), "checkpoint": reference(run_dir / "checkpoint.json")},
            "retry_implementation_snapshots": snapshots,
            "canonical_acceptance_allowed": False,
            "pass": retry["frozen_policy_satisfied"] and not any(not p["both_branch_raw_replays_retained"] for p in pairs)}


def independent_details() -> dict:
    from ioabench.runtime.synthetic_human import persona_for_case, PERSONA_SYSTEM
    datasets, simulations, model_ids = [], [], {}
    for suite, version in FROZEN_VERSIONS.items():
        directory = ROOT / "data/datasets" / suite / version
        cases = [json.loads(line) for line in (directory / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        cache_path = directory / "independent-semantic-validation-cache.json"
        cache = read_json(cache_path)
        cached = {row["candidate_id"]: row for row in cache["results"]}
        models = cache["validator_models"]
        checks = {"independent_model_ids": len(models) == len(set(models)) == 2 and "deepseek-v4.1-flash" not in models,
                  "cache_prompt_signature": cache["cache_signature"] == canonical_sha256({"models": models, "prompt_version": "semantic-visible-v2"}),
                  "exact_coverage": Counter(r["candidate_id"] for r in cache["results"]) == Counter(c["candidate_id"] for c in cases),
                  "input_hashes": all(cached[c["candidate_id"]]["input_sha256"] == canonical_sha256({"candidate_id": c["candidate_id"], "sut_payload": c["sut_payload"]}) for c in cases),
                  "two_accepted_verdicts": all(r["accepted"] and len(r["verdicts"]) == 2 and [v["metadata"].get("model_id") for v in r["verdicts"]] == models and all(v["label"] == "ACCEPT" and not v["metadata"].get("provider_validation_failed") for v in r["verdicts"]) for r in cached.values()),
                  "rejections_retained": (directory / "rejected.jsonl").is_file()}
        datasets.append({"suite": suite, "version": version, "checks": checks, "pass": all(checks.values()),
                         "cache_evidence": reference(cache_path), "limitations": "Cache stores verdicts and exact visible-input hashes; original validator response bodies are not in this cache."})
        results = read_json(ROOT / "data/runs" / f"deepseek-v4.1-flash-{suite}-{version}-formal" / "results.json")
        raw_models = Counter()
        for unit, value in results.items():
            replay = value["replay"]
            sh_records = []
            for record in replay["model_records"]:
                if record["request"].get("role_metadata", {}).get("role") == "SYNTHETIC_HUMAN":
                    sh_records.append(record)
                else:
                    raw_models[record["response"].get("provider_metadata", {}).get("model", "UNKNOWN")] += 1
            if suite not in {"T361", "T362", "T363"}:
                continue
            expected_persona = persona_for_case(replay["case_id"])["persona_id"]
            sh_manifest = replay["scenario"]["manifest"]["synthetic_human"]
            sh_checks = {"persona_assignment": sh_manifest["persona_id"] == expected_persona,
                         "simulation_only": value["eligibility"] == "SIMULATION_ONLY" and replay["scenario"]["simulation_only"] is True,
                         "independent_model": sh_manifest["model_id"] == "glm-5.3-flash" and all(r["response"]["model_id"] == "glm-5.3-flash" for r in sh_records),
                         "two_message_isolated_requests": all(len(r["request"]["messages"]) == 2 and r["request"]["messages"][0] == {"role": "system", "content": PERSONA_SYSTEM} and r["request"]["messages"][1]["role"] == "user" and r["request"]["role_metadata"]["persona_id"] == expected_persona for r in sh_records),
                         "completed_cases_have_sh_calls": value["status"] != "COMPLETED" or bool(sh_records)}
            simulations.append({"suite": suite, "unit_id": unit, "persona_id": expected_persona, "sh_records": len(sh_records),
                                "raw_provider_model_ids": dict(Counter(r["response"].get("provider_metadata", {}).get("model", "UNKNOWN") for r in sh_records)),
                                "checks": sh_checks, "pass": all(sh_checks.values())})
        model_ids[suite] = dict(raw_models)
    t311_results = read_json(ROOT / "data/runs/deepseek-v4.1-flash-T311-2.0.0-formal/results.json")
    runtime_path = ROOT / "src/ioabench/runtime/t311_construct.py"
    runtime = runtime_path.read_bytes()
    reconstructed_hash = hashlib.sha256(runtime.replace(b'"max_tokens": 8192', b'"max_tokens": 4096')).hexdigest()
    t311_checks = {"only_cap_change_reconstructs_every_runtime_hash": all(v["manifest"]["runtime_sha256"] == reconstructed_hash for v in t311_results.values()),
                   "contract_exact_content_match": all(v["manifest"]["construct_contract_sha256"] == sha256(ROOT / "contracts/constructs/T311.json") for v in t311_results.values()),
                   "scorer_exact_content_match": all(v["manifest"]["scorer_sha256"] == sha256(ROOT / "src/ioabench/suites/t311/construct_scoring.py") for v in t311_results.values())}
    return {"artifact": "V32_INDEPENDENT_DETAIL_EVIDENCE", "version": "3.2.0", "provider_calls": 0,
            "dataset_validator_bindings": datasets, "synthetic_human_cases": simulations,
            "provider_reported_tested_model_ids": model_ids, "t311_byte_reconstruction": t311_checks,
            "source_evidence": [reference(runtime_path), reference(ROOT / "src/ioabench/runtime/synthetic_human.py"), reference(ROOT / "src/ioabench/models/aihubmix.py")],
            "pass": all(r["pass"] for r in datasets + simulations) and all(t311_checks.values()),
            "limits": ["This artifact verifies retained evidence; it does not recover discarded attempts or paired branches.",
                       "The adapter's response.model_id copies the requested ID. provider_metadata.model is separately enumerated without assuming aliases are identical."]}


def prepare_corrective_patch() -> dict:
    changes = {
        "src/ioabench/runtime/batch.py": [('"UNSUPPORTED", "INVALID_RUN",', '"UNSUPPORTED", "INVALID_MODEL_OUTPUT", "INVALID_RUN",')],
        "src/ioabench/runtime/discovery_selection.py": [
            ('"outcome_class": paired_result["score"].get("outcome_class")}', '"outcome_class": paired_result["score"].get("outcome_class"), "replay": paired_result["replay"]}'),
            ("'2.1.0' if suite_id == 'T353'", "'2.2.0' if suite_id == 'T353'")],
        "src/ioabench/suites/t353/construct_scoring.py": [('"counterfactual_selection_delta": paired_delta or float(manipulated)', '"counterfactual_selection_delta": paired_delta')],
        "src/ioabench/runtime/construct_dispatch.py": [('DISPATCH_VERSION = "construct-dispatch-1.0.0"', 'DISPATCH_VERSION = "construct-dispatch-1.0.1"')],
    }
    diff, fingerprints = [], []
    for relative, replacements in changes.items():
        path = ROOT / relative
        before = path.read_text(encoding="utf-8")
        after = before
        for old, new in replacements:
            if after.count(old) != 1:
                raise ValueError(f"corrective patch context is ambiguous: {relative}")
            after = after.replace(old, new, 1)
        compile(after, relative, "exec")
        fingerprints.append({"path": relative, "before_sha256": sha256(path),
                             "proposed_utf8_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest()})
        diff.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile="a/" + relative, tofile="b/" + relative))
    target = ROOT / "artifacts/scientific_closure_v3_2/proposed-corrective-release.patch"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(diff))
    return {"artifact": "CORRECTIVE_RELEASE_PATCH_PROPOSAL", "version": "3.2.0", "patch": reference(target),
            "files": fingerprints, "pass": True, "applied_to_active_source": False,
            "validation": "All four proposed Python files compile; behavioral validation must run in an isolated candidate before release.",
            "approval_boundary": "Corrective runtime/scorer semantics require a separately versioned release decision. No provider run is authorized by this proposal."}


def closure_report() -> dict:
    inventory_path = ROOT / "artifacts/gates/V32_S0_EVIDENCE_INVENTORY.json"
    impact_path = ROOT / "artifacts/gates/V32_S1_POLICY_IMPACT_v2.json"
    trace_path = ROOT / "artifacts/scientific_closure_v3_2/trace-full-001.json"
    detail_path = ROOT / "artifacts/scientific_closure_v3_2/independent-details-001.json"
    inventory_data, impact, trace, details = map(read_json, (inventory_path, impact_path, trace_path, detail_path))
    changed = impact["historical_observations"]["confirmed_invalid_count_decreases"]
    impacted = {row["suite"] for row in changed}
    pair_issue = impact["t353_pair_replay"]
    names = {s: read_json(ROOT / "contracts/constructs" / f"{s}.json")["construct_name"] for s in FROZEN_VERSIONS}
    evidence = [reference(p) for p in (inventory_path, impact_path, trace_path, detail_path)]
    total_changes = sum(r["minimum_previously_invalid_no_longer_invalid"] for r in changed)
    claims = [
        {"claim": "18 datasets and 1620 terminal results are present and correctly hash-bound", "verdict": "CONFIRMED", "evidence": reference(inventory_path)},
        {"claim": "Retained primary trajectories can be reproduced under current code", "verdict": "CONFIRMED", "scope": "1440 exact; T311 90 with disclosed cap diagnostic; T353 90 primary-only diagnostic, counterfactual metric excluded", "evidence": reference(trace_path)},
        {"claim": "INVALID_MODEL_OUTPUT was never retried", "verdict": "CONTRADICTED", "minimum_invalid_count_decrease": total_changes, "suites": sorted(impacted), "evidence": reference(impact_path)},
        {"claim": "All T353 counterfactual model trajectories are fully replayable", "verdict": "CONTRADICTED", "missing_cases": pair_issue["raw_pair_replays_missing"], "evidence": reference(impact_path)},
        {"claim": "T353 counterfactual_selection_delta equals the difference between paired selections", "verdict": "CONTRADICTED", "observed_mismatches": len(pair_issue["pair_delta_mismatches"]), "evidence": reference(impact_path)},
        {"claim": "T311 runtime difference is only the max_tokens constant, contract and scorer unchanged", "verdict": "CONFIRMED", "evidence": reference(detail_path)},
        {"claim": "Every run has one unchanging source hash", "verdict": "CONTRADICTED", "suites": [r["suite"] for r in inventory_data["suites"] if len(r["case_source_hashes"]) != 1 or r["run_source_sha256"] not in r["case_source_hashes"]], "scope": "This is provenance drift, not by itself evidence of changed observed semantics."},
    ]
    independent = {"artifact": "CODEX_INDEPENDENT_REVERIFICATION", "version": "3.2.0-preliminary-1", "verdict": "CONTRADICTED",
                   "claims": claims, "evidence": evidence, "pass": False, "provider_calls": 0,
                   "remaining_work": ["Recover original case-level terminal attempts where possible; aggregate counts alone do not identify the changed case IDs.", "Complete per-path source/profile and T311 provider-history review before binding unaffected candidates.", "A corrective runtime/scorer release requires explicit user decision."]}
    write_new(ROOT / "artifacts/gates/CODEX_INDEPENDENT_REVERIFICATION.json", independent)
    t311 = next(r for r in inventory_data["suites"] if r["suite"] == "T311")
    deviation = {"artifact": "T311_CANONICAL_DEVIATION", "version": "3.2.0-preliminary-1", "verdict": "UNKNOWN",
                 "observed_ceiling": {"records": t311["model_records"], "maximum_completion_tokens": t311["maximum_completion_tokens"], "finish_reasons": t311["finish_reasons"], "missing_usage": t311["records_missing_completion_usage"]},
                 "byte_identity_checks": details["t311_byte_reconstruction"],
                 "trajectory_reproduction": "90/90 match after cap-only diagnostic normalization; this does not model provider counterfactual outputs",
                 "concurrency": {"recorded": 1, "target": 3, "local_case_state": "fresh per execution", "systematic_provider_rate_limit_effect": "UNKNOWN_NO_COMPLETE_ATTEMPT_HISTORY"},
                 "rerun_required": "UNDETERMINED", "evidence": evidence,
                 "reason": "The ceiling was not reached and code/contract differences are resolved. The protocol's provider-side concurrency condition remains unproven; no automatic rerun is authorized."}
    write_new(ROOT / "artifacts/gates/T311_CANONICAL_DEVIATION.json", deviation)
    bindings = []
    for row in inventory_data["suites"]:
        suite = row["suite"]
        proven_issue = suite in impacted or (suite == "T353" and (pair_issue["raw_pair_replays_missing"] or pair_issue["pair_delta_mismatches"]))
        bindings.append({"suite": suite, "name": names[suite], "run_id": row["run_id"],
                         "dataset_binding": row["dataset_binding"], "run_source_sha256": row["run_source_sha256"],
                         "case_source_hashes": row["case_source_hashes"],
                         "source_relation": "STRICT_SOURCE_IDENTITY" if set(row["case_source_hashes"]) == {inventory_data["release_source_sha256"]} and row["run_source_sha256"] == inventory_data["release_source_sha256"] else "RETAINED_TRAJECTORY_REEXECUTION_AVAILABLE",
                         "prompt_tool_inventory": row["prompt_tool_inventory"], "profile_evidence": row["tested_parameters"],
                         "runtime_scorer_evidence": reference(trace_path), "relevant_diff_evidence": reference(impact_path),
                         "binding_level": "INCOMPATIBLE" if proven_issue else "UNPROVEN",
                         "canonical_accepted": False, "rerun_required": "UNDETERMINED_PENDING_RECOVERY_AND_USER_DECISION",
                         "reason": "Observed violation of frozen retry policy" if suite in impacted else "Missing paired raw records and observed counterfactual metric conflict" if suite == "T353" else "No invalidation inferred; remaining binding review has not completed",
                         "evidence": row["evidence"]})
    binding_report = {"artifact": "RETROACTIVE_RELEASE_BINDING_AUDIT", "version": "3.2.0-preliminary-1", "base_release": reference(RELEASE),
                      "verdict": "NOT_ACCEPTED", "pass": False, "suites": bindings,
                      "limits": "INCOMPATIBLE here rejects canonical qualification under the frozen policy; it does not delete or invalidate all retained observations. UNPROVEN does not imply rerun."}
    write_new(ROOT / "artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT.json", binding_report)
    for artifact, reason in {
        "BENCHMARK_IMPLEMENTATION_ACCEPTANCE": "Shared resume-policy mismatch and T353 counterfactual metric/replay defects remain in frozen implementation.",
        "CANONICAL_BINDING_ACCEPTANCE": "Five candidate runs have observed policy or evidence conflicts; other binding reviews remain open.",
        "DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE": "Canonical binding is not accepted; 1620 terminal records alone do not satisfy campaign acceptance.",
        "FINAL_PROJECT_ACCEPTANCE_V3_2": "S1/S3/S5 not passed; no accepted canonical report, addendum or final delivery can be published yet.",
    }.items():
        write_new(ROOT / "artifacts/gates" / f"{artifact}.json", {"artifact": artifact, "version": "3.2.0-preliminary-1",
                    "verdict": "NOT_ACCEPTED", "pass": False, "reason": reason, "evidence": evidence,
                    "historical_gate_preserved": "artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json"})
    dataset_checks = {"18_content_bindings": all(r["dataset_binding"]["pass"] for r in inventory_data["suites"]),
                      "18_independent_validator_cache_bindings": all(r["pass"] for r in details["dataset_validator_bindings"])}
    write_new(ROOT / "artifacts/gates/DATASET_PACK_ACCEPTANCE.json", {"artifact": "DATASET_PACK_ACCEPTANCE", "version": "3.2.0-preliminary-1",
              "verdict": "PASS" if all(dataset_checks.values()) else "FAIL", "pass": all(dataset_checks.values()), "checks": dataset_checks,
              "scope": "Reconfirmed content, identity and retained independent-validation evidence for unchanged authoritative datasets. No new generation or semantic judging.", "evidence": evidence})
    lines = ["# IoA-Bench v3.2 独立复核（初步结论）", "", "当前结论：原来的全部追认建议不成立，最终验收暂不通过。历史数据、Run、Release 和 Gate 均保留。", "",
             "本次没有 Provider 调用。审计代码重算数据、Manifest、Replay 和请求哈希，并用保存的回复驱动当前运行时。16 项共 1,440 条轨迹完全重现；资格伪装（T311）90 条在仅归一化 token 上限后重现；节点操纵（T353）90 条主轨迹单独重现，配对分支因缺原始回复不能重现。", "",
             "## 已证实的恢复执行问题", "", "冻结策略把 INVALID_MODEL_OUTPUT 作为终态。实际 BatchRunner 在恢复时再次执行这些 case。独立临时目录复现已确认，9 个历史 ZIP 中该文件与当前版本相同。历史导出的工具输出还记录了以下变化；下限不是准确的受影响 case 名单。", "",
             "| 测评 | 早期无效输出 | 最终无效输出 | 至少有多少条原无效输出不再无效 |", "|---|---:|---:|---:|"]
    for row in changed:
        lines.append(f"| {row['suite']} {names[row['suite']]} | {row['earlier_counts'].get('INVALID_MODEL_OUTPUT', 0)} | {row['final_counts'].get('INVALID_MODEL_OUTPUT', 0)} | {row['minimum_previously_invalid_no_longer_invalid']} |")
    lines += ["", f"合计下限：{total_changes} 条。当前已完成的 safe/unsafe 结果在恢复器中会被跳过；已证实的问题是无效输出被重试后改变统计口径。原始失败尝试没有完整的 case 级不可变记录，不能仅靠数量恢复原结果，也不能把四套全部 360 条都称为已被证明受影响。", "",
              "## 节点操纵（T353）", "", f"90 个案例的两个配对分支只保存选择、效用和 outcome 摘要，没有原始 ModelRequest/ModelResponse、动作和世界状态。此外，{len(pair_issue['pair_delta_mismatches'])} 条记录的两次选择相同，但 counterfactual_selection_delta 为 1；评分器把主轨迹被操纵标志合并进了差异指标。", "",
              "主轨迹的动作、世界状态以及除该配对指标外的评分可重现，现有主要结果应保留。修复范围应先限定于丢失的配对证据和该指标；尚未授权任何重跑。", "",
              "## 资格伪装（T311）", "", f"647 条模型记录中最大 completion_tokens 为 {t311['maximum_completion_tokens']}，无 length 截断。当前运行时只把 8192 改回 4096，即可重建记录中的完整文件哈希；契约与评分器也逐字节一致。并发的本地 case 隔离已由源码与重现支持，但原协议要求的 Provider 系统性限流影响缺完整尝试历史，故偏差总判定暂为 UNKNOWN，不把它转成自动重跑要求。", "",
              "## 已通过与未完成", "", "18 套数据的三方内容绑定、90 个唯一 case、难度与条件配比，以及两个独立验证器的逐 case 输入哈希和 verdict 均通过。270 条合成人类模拟结果的固定 persona、独立两消息请求、1,045 条合成人类调用与 SIMULATION_ONLY 标志已核对；讨论扭曲和能动性弱化的重试问题仍影响其 canonical 资格。", "",
              "当前源码与基础 Release 哈希一致。部分 Run 的 case 级 source hash 在运行期间发生变化，不能只列 Run Manifest 的 8 个 hash；已保存完整分组。逐轨迹重现通过能证明保留轨迹一致，不能证明所有历史尝试都被保留。", "",
              "## 后续边界", "", "修复差异位于 `artifacts/scientific_closure_v3_2/proposed-corrective-release.patch`，未应用到冻结源码，四个拟修改 Python 文件已通过语法检查。批准新的修复版本后，应在隔离副本验证，再冻结最小受影响 case/分支清单与 Provider 预算；原案例级记录若能恢复，应优先恢复。", "",
              "参考：`artifacts/gates/V32_S1_POLICY_IMPACT_v2.json`、`CODEX_INDEPENDENT_REVERIFICATION.json`、`RETROACTIVE_RELEASE_BINDING_AUDIT.json`。外部对话导出含凭据，因此仅保存文件哈希、工具 part_id、聚合计数和选定无凭据片段，不把完整导出放入交付包。", ""]
    report_path = ROOT / "artifacts/reports/codex_independent_reverification.md"
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    table = ["# Run 与 Release 绑定审计（初步）", "", "基础版本：v3-20260930。当前没有新的 canonical 接受声明；INCOMPATIBLE 为已证实的冻结规则冲突，UNPROVEN 为审查未完成。两者都不自动授权重跑。", "", "| 测评 | 数据版本 | 源码关系 | 绑定等级 |", "|---|---|---|---|"]
    for row in bindings:
        table.append(f"| {row['suite']} {row['name']} | {FROZEN_VERSIONS[row['suite']]} | {row['source_relation']} | {row['binding_level']} |")
    with (ROOT / "artifacts/reports/retroactive_release_binding_audit.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(table) + "\n")
    return {"artifact": "V32_CLOSURE_REPORT_BUILD", "report": reference(report_path), "pass": False,
            "minimum_invalid_count_decrease": total_changes, "confirmed_affected_suites": sorted(impacted | {"T353"}),
            "goal_complete": False, "provider_calls": 0}


def state_check(root: Path = ROOT) -> dict:
    """Validate governance structure without certifying old task completion."""
    from graphlib import TopologicalSorter, CycleError
    import yaml
    queue_path, state_path = root / "state/WORK_QUEUE.yaml", root / "state/PROJECT_STATE.yaml"
    queue = yaml.safe_load(queue_path.read_text(encoding="utf-8"))
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    items = queue["items"]
    by_id = {item["id"]: item for item in items}
    dependencies = {key: set(item.get("depends_on", [])) for key, item in by_id.items()}
    missing = sorted({dep for values in dependencies.values() for dep in values if dep not in by_id})
    try:
        tuple(TopologicalSorter(dependencies).static_order())
        acyclic = True
    except CycleError:
        acyclic = False
    active = sorted(key for key, item in by_id.items() if item["status"] == "in_progress" and item.get("execution_scope") != "historical")
    historical = sorted(key for key, item in by_id.items() if item["status"] == "in_progress" and item.get("execution_scope") == "historical")
    missing_evidence = []
    for item in items:
        evidence = item.get("evidence", [])
        for relative in [evidence] if isinstance(evidence, str) else evidence:
            if not (root / relative).is_file():
                missing_evidence.append(relative)
    checks = {
        "unique_ids": len(by_id) == len(items),
        "task_counts_match": len(items) == queue["summary"]["task_count"] == state["work_queue_task_count"],
        "versions_match": queue["version"] == state["work_queue_version"],
        "all_dependencies_resolve": not missing,
        "dag_acyclic": acyclic,
        "valid_statuses": all(item["status"] in queue["queue_policy"]["status_values"] for item in items),
        "milestones_resolve": all(item["milestone"] in queue["milestones"] for item in items),
        "milestone_exits_resolve": all(m["exit_task"] in by_id for m in queue["milestones"].values()),
        "active_state_matches_queue": active == sorted(state["in_progress"]),
        "next_task_resolves": ((not state.get("next") and state.get("next_task") in {None, "none"})
                               or (state.get("next_task") in by_id
                                   and state.get("next_task") in state.get("next", []))),
        "recorded_evidence_exists": not missing_evidence,
    }
    return {"artifact": "WORK_QUEUE_STRUCTURE_VALIDATION", "pass": all(checks.values()),
            "work_queue_version": queue["version"], "task_count": len(items), "checks": checks,
            "in_progress_tasks": active, "historical_in_progress_tasks": historical,
            "missing_dependencies": missing, "missing_evidence": missing_evidence,
            "milestone_counts": dict(Counter(item["milestone"] for item in items)),
            "status_counts": dict(Counter(item["status"] for item in items)),
            "source_hashes": {str(p.relative_to(root)): sha256(p) for p in (queue_path, state_path)},
            "scope": "Structure and current state linkage only; historical done labels and scientific gate acceptance are not re-certified."}


def windows_snapshot_hash(files: dict[str, bytes]) -> str:
    """Match frozen Windows Path ordering, including its case-insensitive sort."""
    from pathlib import PureWindowsPath
    digest = hashlib.sha256()
    for directory in ("src", "contracts", "config"):
        for name in sorted((n for n in files if n.startswith(directory + "/")), key=PureWindowsPath):
            digest.update(name.encode("utf-8"))
            digest.update(hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


def observed_model_profiles() -> dict:
    """Describe recorded settings and source defaults without inventing provider facts."""
    suites = []
    for suite, version in FROZEN_VERSIONS.items():
        run_id = f"deepseek-v4.1-flash-{suite}-{version}-formal"
        directory = ROOT / "data/runs" / run_id
        results_path = directory / "results.json"
        manifest_path = directory / "manifest" / f"{run_id}.json"
        manifest = read_json(manifest_path)
        roles, records = {}, []
        for unit, result in read_json(results_path).items():
            for record in result["replay"]["model_records"]:
                request, response = record["request"], record["response"]
                assert canonical_sha256(request) == record["request_sha256"]
                role = request.get("role_metadata", {}).get("role", "UNKNOWN")
                group = roles.setdefault(role, {"parameters": Counter(), "requested_model_ids": Counter(),
                    "provider_returned_model_ids": Counter(), "system_prompt_hashes": set(), "tool_schema_hashes": set()})
                parameters = request["parameters"]
                group["parameters"][json.dumps(parameters, sort_keys=True)] += 1
                group["requested_model_ids"][response.get("model_id", "MISSING")] += 1
                group["provider_returned_model_ids"][str(response.get("provider_metadata", {}).get("model", "UNKNOWN_NOT_RETAINED"))] += 1
                system = canonical_sha256([m for m in request["messages"] if m["role"] == "system"])
                tools = canonical_sha256(request["tools"])
                group["system_prompt_hashes"].add(system)
                group["tool_schema_hashes"].add(tools)
                records.append({"unit_id": unit, "case_id": result["case_id"], "record_id": record["record_id"], "role": role,
                    "request_sha256": record["request_sha256"], "system_prompt_sha256": system,
                    "initial_task_sha256": canonical_sha256(next((m for m in request["messages"] if m["role"] == "user"), None)),
                    "tool_schema_sha256": tools})
        normalized = {}
        for role, group in roles.items():
            profiles = []
            for encoded, count in group["parameters"].items():
                parameters = json.loads(encoded)
                profiles.append({"record_count": count, "explicit_parameters": parameters,
                    "top_p": parameters.get("top_p", "PROVIDER_DEFAULT_UNSET"),
                    "reasoning": {k: v for k, v in parameters.items() if "reason" in k or "think" in k} or "PROVIDER_DEFAULT_UNSET",
                    "tool_choice": parameters.get("tool_choice", "PROVIDER_DEFAULT_UNSET"),
                    "response_format": parameters.get("response_format", "PROVIDER_DEFAULT_UNSET")})
            normalized[role] = {"profiles": profiles, "requested_model_ids": dict(group["requested_model_ids"]),
                "provider_returned_model_ids": dict(group["provider_returned_model_ids"]),
                "system_prompt_hashes": sorted(group["system_prompt_hashes"]), "tool_schema_hashes": sorted(group["tool_schema_hashes"])}
        suites.append({"suite": suite, "run_id": run_id, "roles": normalized, "records": records,
            "initial_manifest_concurrency": manifest["runtime"].get("execution_concurrency", "UNKNOWN_NOT_RETAINED"),
            "actual_concurrency_on_each_resume": "UNKNOWN_NOT_PERSISTED",
            "evidence": [reference(manifest_path), reference(results_path)]})
    return {"artifact": "OBSERVED_MODEL_PROFILE_AND_PROMPT_TOOL_PROVENANCE", "version": "3.2.0-1", "pass": True,
        "canonical_acceptance": False, "provider_calls": 0, "suites": suites,
        "source_derived_transport": {"provider_adapter": "AIHubMixAdapter", "endpoint_family": "/chat/completions",
            "configured_base_urls": ["https://aihubmix.com/v1", "https://api.inferera.com/v1"],
            "actual_base_url_per_call": "UNKNOWN_NOT_PERSISTED", "timeout_seconds_per_transport_attempt": 300,
            "transient_outer_attempt_limit": 3, "transient_sleep_seconds": [1.5, 3.0, 4.5],
            "per_attempt_fallbacks": "Transport may try both configured hosts; 3 is not a total HTTP-request bound.",
            "context_window": "UNKNOWN_NOT_PERSISTED", "live_discovery_response": "NOT_RETAINED_IN_FORMAL_RUN_MANIFEST",
            "source": reference(ROOT / "src/ioabench/models/aihubmix.py")},
        "scheduler": {"profile": reference(ROOT / "config/scheduler_profile.json"),
            "implementation": reference(ROOT / "src/ioabench/cli.py"),
            "actual_selection": "CLI reads IOABENCH_CONCURRENCY (default 1), not scheduler_profile.json; manifest records only initial value.",
            "retry_conflict": reference(ROOT / "artifacts/gates/V32_S1_POLICY_IMPACT_v2.json")},
        "limits": ["This is observed metadata with explicit unknowns, not a Release addendum or canonical acceptance.",
            "ModelResponse.model_id copies the requested ID; provider_metadata.model is recorded separately and may be an alias.",
            "Source-derived transport settings are not per-call host/attempt evidence.",
            "Missing T353 paired raw requests are not represented in this inventory."]}


def source_compatibility() -> dict:
    from itertools import product
    from pathlib import PureWindowsPath
    from ioabench.runtime.construct_dispatch import RUNNERS
    current = {p.relative_to(ROOT).as_posix(): p.read_bytes() for directory in ("src", "contracts", "config")
               for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    current_hash = windows_snapshot_hash(current)
    assert current_hash == source_tree_hash(ROOT)
    inventory_path = ROOT / "artifacts/gates/V32_S0_EVIDENCE_INVENTORY.json"
    inventory = read_json(inventory_path)
    assert current_hash == inventory["current_source_sha256"]
    targets = {h for row in inventory["suites"] for h in row["case_source_hashes"]}
    snapshots, known, archives = {}, {current_hash: current}, []
    for path in sorted(ARCHIVE_DIR.glob("*.zip")):
        with ZipFile(path) as archive:
            files = {n: archive.read(n) for n in archive.namelist() if n.startswith(("src/", "contracts/", "config/"))
                     and not n.endswith("/") and "__pycache__" not in n.split("/")}
        digest = windows_snapshot_hash(files)
        archives.append({**reference(path), "source_sha256": digest, "files": len(files)})
        snapshots[path.name] = files
        if digest in targets:
            known[digest] = files
    old_name = "IoA-Bench-current-workspace-handoff-20260929-latest.zip"
    old = snapshots[old_name]
    names = [n for d in ("src", "contracts", "config")
             for n in sorted((n for n in old.keys() | current.keys() if n.startswith(d + "/")), key=PureWindowsPath)]
    changed = [n for n in names if old.get(n) != current.get(n)]
    assert len(changed) <= 18, "Review the larger search space before expanding reconstruction"
    # Search only preserved old/current bytes. A matching frozen hash proves the
    # exact reconstructed file set; unmatched intermediate edits remain unknown.
    chunks, pending, variants = [], b"", []
    for name in names:
        def piece(value):
            return name.encode("utf-8") + hashlib.sha256(value).digest() if value is not None else b""
        if name in changed:
            chunks.append((pending,))
            chunks.append((piece(old.get(name)), piece(current.get(name))))
            pending = b""
            variants.append(name)
        else:
            pending += piece(current[name])
    chunks.append((pending,))
    reconstructions = {}
    for choices in product((0, 1), repeat=len(variants)):
        payload = b"".join(chunk[choices[(i - 1) // 2]] if i % 2 else chunk[0] for i, chunk in enumerate(chunks))
        digest = hashlib.sha256(payload).hexdigest()
        if digest not in targets or digest in known:
            continue
        files = dict(old)
        selection = dict(zip(variants, choices))
        for name, choice in selection.items():
            if choice:
                if name in current:
                    files[name] = current[name]
                else:
                    files.pop(name, None)
        assert windows_snapshot_hash(files) == digest
        known[digest] = files
        reconstructions[digest] = {"base_archive": old_name, "current_byte_paths": [n for n, c in selection.items() if c],
                                   "file_hashes": {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}}
    rows = []
    for row in inventory["suites"]:
        suite = row["suite"]
        adapter, _, executor, _ = RUNNERS[suite]
        critical = {"src/" + m.replace(".", "/") + ".py" for m in (adapter, executor)}
        critical |= {f"src/ioabench/suites/{suite.lower()}/construct_scoring.py", f"contracts/constructs/{suite}.json",
                     "src/ioabench/models/aihubmix.py", "src/ioabench/runtime/batch.py", "src/ioabench/runtime/scientific_io.py",
                     "src/ioabench/runtime/construct_dispatch.py", "src/ioabench/cli.py"}
        groups = []
        for digest, count in row["case_source_hashes"].items():
            files = known.get(digest)
            differences = None if files is None else [{"path": n,
                "recorded_source_sha256": hashlib.sha256(files[n]).hexdigest() if n in files else None,
                "release_sha256": hashlib.sha256(current[n]).hexdigest() if n in current else None,
                "direct_runtime_or_control_path": n in critical}
                for n in sorted(files.keys() | current.keys()) if files.get(n) != current.get(n)]
            groups.append({"recorded_source_sha256": digest, "case_count": count,
                           "source_bytes_resolved": files is not None, "differences": differences,
                           "reconstruction": "PRESERVED_BYTE_COMBINATION" if digest in reconstructions else "ARCHIVE_OR_CURRENT" if files is not None else "UNRESOLVED"})
        rows.append({"suite": suite, "run_id": row["run_id"], "groups": groups,
                     "resolved_case_count": sum(g["case_count"] for g in groups if g["source_bytes_resolved"]),
                     "critical_release_files": {n: hashlib.sha256(current[n]).hexdigest() for n in sorted(critical) if n in current}})
    return {"artifact": "RECORDED_SOURCE_BYTE_RECOVERY", "version": "3.2.0-1", "pass": True,
            "canonical_acceptance": False, "provider_calls": 0, "current_source_sha256": current_hash,
            "source_hash_ordering": "Windows pathlib ordering; no source-hash algorithm was modified",
            "inventory": reference(inventory_path), "archives": archives, "reconstructions": reconstructions,
            "search_space": 2 ** len(variants), "variant_paths": variants, "suites": rows,
            "resolved_cases": sum(row["resolved_case_count"] for row in rows),
            "limits": ["Recorded source hashes describe disk bytes when sampled, not an attestation of every loaded Python code object.",
                       "Source recovery alone does not establish runtime/profile equivalence, complete attempt history or canonical qualification.",
                       "Direct path flags are navigation aids, not a transitive dependency proof."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("baseline", "verify-baseline", "inventory", "trace-replay", "policy-impact", "details", "prepare-fix", "report", "state-check", "source-compatibility", "observed-profiles"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--suite", default="all", choices=("all", *FROZEN_VERSIONS))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--t311-cap-diagnostic", action="store_true")
    parser.add_argument("--t353-main-only", action="store_true")
    parser.add_argument("--history-export", type=Path)
    args = parser.parse_args()
    if args.command == "trace-replay":
        result = trace_replay(args.suite, args.limit, args.t311_cap_diagnostic, args.t353_main_only)
    elif args.command == "policy-impact":
        if not args.history_export:
            parser.error("policy-impact requires --history-export")
        result = policy_impact(args.history_export)
    else:
        result = {"baseline": baseline, "verify-baseline": verify_baseline, "inventory": inventory, "details": independent_details, "prepare-fix": prepare_corrective_patch, "report": closure_report, "state-check": state_check, "source-compatibility": source_compatibility, "observed-profiles": observed_model_profiles}[args.command]()
    if args.output:
        write_new(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"suites", "files", "historical_observations", "t353_pair_replay", "retry_implementation_snapshots", "dataset_validator_bindings", "synthetic_human_cases", "provider_reported_tested_model_ids", "reconstructions", "archives"}}, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
