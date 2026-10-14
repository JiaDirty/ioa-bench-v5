"""Build a synthetic v4-conformant run directory to exercise the Phase F validator.

This is a TEST FIXTURE ONLY.  It lives under a scratch root, never under
data/runs, and is deleted by the accompanying test.  It exists so the validator's
pass path is exercised offline before any provider call is made.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ioabench.hashing import canonical_sha256  # noqa: E402

MODEL = "deepseek-v4.1-flash"


def build(suite: str, scratch: pathlib.Path, release: dict) -> pathlib.Path:
    version = release["datasets"][suite]["version"]
    run_id = f"{MODEL}-{suite}-{version}-v4.1-formal"
    run_dir = scratch / run_id
    (run_dir / "attempts").mkdir(parents=True, exist_ok=True)

    historical = ROOT / "data" / "runs" / f"{MODEL}-{suite}-{version}-formal" / "results.json"
    template = json.loads(historical.read_text(encoding="utf-8"))

    results = {}
    for key, rec in template.items():
        r = copy.deepcopy(rec)
        r["status"] = "COMPLETED"
        r["dispatch"]["dispatch_version"] = "construct-dispatch-1.0.2"
        r["suite"] = suite
        rep = r.get("replay")
        if isinstance(rep, dict):
            rep["run_id"] = run_id
            rep["case_id"] = r["case_id"]
            scenario_manifest = rep.setdefault("scenario", {}).setdefault("manifest", {})
            scenario_manifest["source_tree_sha256"] = release["source_tree_sha256"]
            scenario_manifest["runtime_version"] = release["runtime_versions"][suite]
            scenario_manifest["model_id"] = release["tested_model"]["model_id"]
            scenario_manifest["sampling_parameters"] = {
                "temperature": release["tested_model"]["temperature"],
                "max_tokens": release["tested_model"]["max_tokens"],
            }
            for record in rep.get("model_records", []):
                record.setdefault("response", {})["model_id"] = release["tested_model"]["model_id"]
            r["dispatch"]["runtime_version"] = release["runtime_versions"][suite]
        if suite == "T353" and isinstance(rep, dict):
            # mirror the frozen runtime contract: counterfactual branches under
            # scenario.paired_runs, each with its own nested replay
            scenario = rep.setdefault("scenario", {})
            scenario["paired_runs"] = {
                mode: {
                    "selected_agent_id": "alternate-0001",
                    "task_utility": True,
                    "outcome_class": "TASK_SAFE",
                    "replay": {"bundle_version": "selection-construct-v2",
                               "case_id": r["case_id"], "branch": mode},
                }
                for mode in ("honest", "manipulated")
            }
        # rebuild a self-consistent replay content hash
        if isinstance(rep, dict):
            body = {k: v for k, v in rep.items() if k != "content_sha256"}
            rep["content_sha256"] = canonical_sha256(body)
        journal_path = run_dir / "attempts" / r["case_id"] / "attempt-1.jsonl"
        records = list((r.get("replay") or {}).get("model_records") or [])
        journal_rows = [{"kind": "attempt", "run_id": run_id, "suite_id": suite,
                         "case_id": r["case_id"], "attempt_no": 1}]
        journal_rows.extend({"kind": "model_record", "record": record,
                             "record_sha256": canonical_sha256(record)} for record in records)
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True)
                                           for row in journal_rows) + "\n", encoding="utf-8")
        journal = {"path": journal_path.relative_to(scratch.parent).as_posix(),
                   "sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest()}
        r["attempt_journal"] = journal
        r["attempts"] = [{"attempt_no": 1, "status": r["status"],
                          "model_records_produced": len(records),
                          "valid_model_behavior_observed": bool(records),
                          "infrastructure_failure": False,
                          "attempt_journal": journal}]
        r["attempt_no"] = 1
        results[key] = r

    (run_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return run_dir


def build_manifest(suite: str, scratch: pathlib.Path, release: dict,
                   release_sha: str) -> pathlib.Path:
    version = release["datasets"][suite]["version"]
    out = scratch / "manifests"
    out.mkdir(parents=True, exist_ok=True)
    man = {
        "benchmark": {
            "dataset_hashes": {suite: release["datasets"][suite]["content_sha256"]},
            "dataset_versions": {suite: version},
            "contract_hashes": {suite: release["contracts"][suite]},
            "scorer_versions": {suite: release["scorer_versions"][suite]},
            "suite_versions": {suite: version},
        },
        "runtime": {"runtime_version": release["runtime_versions"][suite],
                    "source_tree_sha256": release["source_tree_sha256"]},
        "provenance": {"model_profile_sha256": release["model_profile_sha256"]},
        "release": {
            "release_id": release["release_id"],
            "release_sha256": release_sha,
            "source_tree_sha256": release["source_tree_sha256"],
            "strict_retry_semantics": True,
        },
        "run_id": f"{MODEL}-{suite}-{version}-v4.1-formal",
    }
    p = out / f"{man['run_id']}.manifest.json"
    p.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime = scratch / "runs" / man["run_id"] / "manifest" / f"{man['run_id']}.json"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_bytes(p.read_bytes())
    return p
