"""Derive the BLOCKED Round02 handoff from retained evidence; sends no network requests."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tests(path):
    suites = list(ET.parse(path).getroot().iter("testsuite"))
    return {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}


def wilson(success, n):
    if not n:
        return None
    z, p = 1.959963984540054, success / n
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [max(0.0, center-half), min(1.0, center+half)]


def build(out):
    baseline = read(out / "BASELINE.json")
    s1 = read(out / "s1-completion/S1_RESULT.json")
    assert s1["status"] == "BLOCKED", "This settlement implements the blocked S1 branch only."
    attempt_path = out / "s1-completion/model_io" / s1["request_id"] / "attempt-001.json"
    attempt = read(attempt_path)
    assert attempt["category"] == "AUTH/PERMISSION" and '"401"' in attempt["error"]
    regression, negative = tests(out / "PROVIDER_REGRESSION_R2.xml"), tests(out / "FAILOVER_NEGATIVE_TESTS.xml")
    assert all(regression[k] == 0 and negative[k] == 0 for k in ("failures", "errors", "skipped"))
    plan = read(out / "s1-completion/PREREGISTRATION.json")
    catalog = read(out / "s1-completion/CATALOG.json")
    roster = yaml.safe_load((out / "inputs/02_MODEL_CANDIDATES.yaml").read_text(encoding="utf-8"))
    cached = Path("D:/Project/Playground/scrape/aihubmix/.workbuddy/workspace/model-parameters")
    index = read(cached / "index.json")
    by_id = {row["id"]: row for row in index["models"]}
    profiles, rows = [], []
    fields = ("display_name exact_api_id served_id family endpoint effort_sent thinking_mode max_output_sent "
              "input_tokens reasoning_tokens output_tokens price_source usd_estimated elapsed_ms http_code "
              "finish_reason schema_pass tool_loop_pass quality_pass failures attempted confidence evidence_sha").split()
    present = 0
    for item in roster["models"]:
        model = item["candidate_gateway_id"]
        entry = next((row for row in catalog if (row.get("model_id") or row.get("id")) == model), None)
        present += entry is not None
        cached_path = cached / by_id[model]["path"] if model in by_id else None
        schema = read(cached_path) if cached_path else None
        profile = {"display_name": item["display"], "candidate_api_id": model,
                   "live_public_catalog_present": entry is not None, "key_access": "UNVERIFIED",
                   "proposed_protocol_NOT_VERIFIED": item["protocol_preference"],
                   "candidate_efforts_NOT_VERIFIED": item["efforts_to_verify"],
                   "candidate_thinking_modes_NOT_VERIFIED": item.get("thinking_modes_to_verify", []),
                   "official_claim": item["think"], "official_url": item.get("official", item.get("gateway", item.get("aa_source"))),
                   "cached_gateway_schema": {"path": str(cached_path), "sha256": sha(cached_path),
                       "last_verified": schema.get("last_verified"), "protocols": schema.get("protocols"),
                       "specs": schema.get("specs")} if schema else None,
                   "live_gateway_schema": "s1-completion/SCHEMA.json" if model == "mimo-v2.6-pro" else "NOT_FETCHED_S1_BLOCKED",
                   "actual_http_evidence": "S1_HTTP401_NOT_CONFIG_VERIFIED" if model == "mimo-v2.6-pro" else "NOT_RUN",
                   "status": "BLOCKED_S1_AUTH", "activate": False}
        profiles.append(profile)
        row = {key: "NOT_RUN" for key in fields}
        row.update(display_name=item["display"], exact_api_id=model or "UNKNOWN", served_id="UNKNOWN",
                   family=schema.get("vendor", "UNKNOWN") if schema else "UNKNOWN",
                   confidence="NO_CURRENT_COMPLETION_CONFIGURATION_VERIFIED", evidence_sha=sha(out / "s1-completion/CATALOG.json"))
        if model == "mimo-v2.6-pro":
            row.update(endpoint=plan["base_url"] + "/chat/completions", effort_sent="OMITTED_NO_EFFORT_PARAMETER",
                       thinking_mode=plan["parameters"]["thinking"]["type"], max_output_sent=plan["parameters"]["max_completion_tokens"],
                       input_tokens="UNKNOWN", reasoning_tokens="UNKNOWN", output_tokens="UNKNOWN",
                       price_source="S1 live catalog; no returned usage", usd_estimated="UNKNOWN",
                       elapsed_ms=attempt["elapsed_seconds"]*1000, http_code=401, finish_reason="UNKNOWN",
                       failures=1, attempted=1, confidence=json.dumps(wilson(0, 1)), evidence_sha=sha(attempt_path))
        rows.append(row)
    with (out / "SCORECARD_ALL_MODELS.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (out / "MODEL_CATALOG_AND_OFFICIAL_DOC_MATRIX.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        columns = ["display_name", "candidate_api_id", "live_public_catalog_present", "key_access", "official_claim", "official_url", "cached_gateway_schema", "live_gateway_schema", "actual_http_evidence", "status"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], dict) else row[key] for key in columns} for row in profiles)
    (out / "PROFILE_MATRIX.yaml").write_text(yaml.safe_dump({"status": "BLOCKED_S1_NOT_ACTIVE_CONFIG",
        "active_profiles": [], "candidate_profiles": profiles, "frozen_SUT_changed": False,
        "gateway_main_and_backup_are_network_paths_not_proven_healthy_profiles": True}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    prior = ROOT / "artifacts/v5/data_factory/coord-round01-20261019T073200Z"
    old_ledger_path = ROOT / "artifacts/v5/data_factory/next-r1/ALL_USAGE_LEDGER.json"
    old = [{"origin": "R3", "source": str(old_ledger_path.relative_to(ROOT)), "source_sha256": sha(old_ledger_path),
            **{key: row[key] for key in ("attempt_id", "requested_model_id", "request_sha256", "status", "ledger")}}
           for row in read(old_ledger_path)["rows"] if row["status"] == "REQUEST_UNRESOLVED"]
    round01_attempt = prior / "provider/mimo-v2.6-pro/new-unrelated-receipt-1/attempt-001.json"
    old.append({"origin": "Round01", "source": str(round01_attempt.relative_to(ROOT)), "source_sha256": sha(round01_attempt),
                **{key: value for key, value in read(round01_attempt).items() if key in {"attempt_id", "request_id", "requested_model_id", "request_sha256", "status"}}})
    assert len(old) == 4 and all(row["request_sha256"] != attempt["request_sha256"] for row in old)
    write(out / "HISTORICAL_UNRESOLVED_REGISTER.json", {"requests": old, "resends": 0,
          "server_status_query": "NOT_RUN_NO_RETURNED_REQUEST_ID_OR_DOCUMENTED_LOOKUP_ENDPOINT", "billing": "UNKNOWN"})
    events = [json.loads(line) for line in (out / "s1-completion/model_io/AIHUBMIX_ATTEMPTS.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(row["event"] == "REQUEST_STARTED" for row in events) == 1
    previous = ""
    with (out / "REQUEST_LEDGER.jsonl").open("w", encoding="utf-8") as stream:
        for value in [{"event": "HISTORICAL_UNRESOLVED_RETAINED_NOT_SENT", **row} for row in old] + events:
            row = {"source_event": value, "previous_event_sha256": previous}
            row["event_sha256"] = canonical_sha256(row)
            previous = row["event_sha256"]
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write(out / "USAGE_AND_COST.json", {"new_completion_attempts": 1, "successful_completion": 0,
        "failed_http401": 1, "new_unresolved": 0, "historic_unresolved": 4, "historic_resends": 0,
        "usage": None, "USD_estimate": None, "billing_status": "UNKNOWN_NOT_ZERO", "valid_engineering_pairs": 0,
        "engineering_cost_per_pair": "NOT_COMPUTABLE", "machine_qualified_cost_per_pair": "NOT_COMPUTABLE",
        "Wilson_95_completion_success": wilson(0, 1), "no_attempt_Wilson": None,
        "denominators": {"preregistered_S1_attempts": 1, "S1_attempted": 1, "S1_success": 0,
                         "S1_failed": 1, "S1_unresolved": 0, "S1_NOT_RUN": 0,
                         "roster_candidates": 17, "roster_without_any_current_POST": 16,
                         "S3_protocol_task_plan": "NOT_FROZEN_S1_BLOCKED", "S4_task_plan": "NOT_FROZEN_S1_BLOCKED"},
        "AA_cost_per_task_included_in_bill": False})
    write(out / "BENCHMARK_TASKSET_FROZEN.json", {"status": "NOT_RUN_S1_BLOCKED", "frozen": False,
          "reason": "No S2/S3 gate; no fair per-config task denominator or quality run established.",
          "requested_Q_topics_only": ["T321-1", "T321-2", "T331-1", "T331-2", "T352-1", "T352-2", "evidence_contradiction", "causal_repair"],
          "planned_weight_prior": roster["configuration"]["model_selection_weights"], "R_two_periods": "NOT_RUN", "B": "NOT_RUN"})
    network = read(out / "network-s1-r2/NETWORK_PATH_DIAGNOSIS.json")
    network["configured_proxy_comparison"] = read(out / "network-s1/aihubmix-configured-wininet.json")
    network.update(s1_gate="BLOCKED_AUTH_PERMISSION", provider_recovered="NO", new_completion_http=401,
                   completion_evidence=str(attempt_path.relative_to(out)), credential_audit="CREDENTIAL_SOURCE_AUDIT.json",
                   root_cause_boundary="Primary direct TCP fails; alternate TLS/HTTP works; completion401 is AUTH_OR_PERMISSION. Exact key/account/channel/upstream cause requires provider/account owner.",
                   historical_rows=[{"origin": "R3", "completion": "HTTP401", "evidence": "artifacts/v5/data_factory/next-r1/AUTH_BLOCKER.md"},
                                    {"origin": "Round01", "completion": "curl28_NO_HTTP", "evidence": "artifacts/v5/data_factory/coord-round01-20261019T073200Z/PROVIDER_DIAGNOSIS.md"},
                                    {"origin": "Round02", "completion": "HTTP401", "evidence": str(attempt_path.relative_to(out))}])
    write(out / "NETWORK_PATH_DIAGNOSIS.json", network)
    changed, missing = [], []
    for name, expected in baseline["protected_files"].items():
        path = ROOT / name
        if not path.is_file():
            missing.append(name)
        elif sha(path) != expected:
            changed.append(name)
    write(out / "PROTECTED_HISTORY.json", {"status": "PASS" if not changed and not missing else "FAIL",
        "checked": len(baseline["protected_files"]), "changed": changed, "missing": missing, "scope": baseline["scope"]})
    assert not changed and not missing
    commands = {"S0": ["git status --short", "git log -1 --format=fuller", "git remote -v"],
                "S1": [f"python -B scripts/v5/diagnose_provider_network.py --out {out.relative_to(ROOT).as_posix()}/network-s1-r2",
                       f"python -B scripts/v5/provider_round02_probe.py --out {out.relative_to(ROOT).as_posix()}/s1-completion --base-url https://api.inferera.com/v1"],
                "S5": [f"python -B -m pytest -p no:cacheprovider tests/v5/test_provider_failover_round02.py tests/v5/test_auxiliary_runtime.py tests/v5/test_provider_round02.py tests/m1 -q --junitxml={out.relative_to(ROOT).as_posix()}/FAILOVER_NEGATIVE_TESTS.xml",
                       f"python -B -m pytest -p no:cacheprovider tests/v5 tests/m1 -q --junitxml={out.relative_to(ROOT).as_posix()}/PROVIDER_REGRESSION_R2.xml"],
                "S6": [f"python -B scripts/v5/settle_provider_round02.py --out {out.relative_to(ROOT).as_posix()}"]}
    stages = []
    for stage, status, limitation in [
        ("S0", "PASS", "Existing writer lock; no new Goal. User-owned untracked directories retained."),
        ("S1", "BLOCKED", "Network alternate reachable; one fresh completion401, no usage/servedID. Stop paid matrix."),
        ("S2", "NOT_RUN", "16/17 public catalog identity matches are S1 metadata only; access/config unverified."),
        ("S3", "NOT_RUN", "No model/protocol/effort matrix after S1 gate failure."),
        ("S4", "NOT_RUN", "No same-task quality, cost, two-period reliability or Pareto ranking."),
        ("S5", "PARTIAL", "Offline Mock guards and actual terminal resume only; real failover NOT_RUN."),
        ("S6", "PARTIAL", "BLOCKED handoff; no active profile or role recommendation.")]:
        stages.append({"stage": stage, "status": status, "commands": commands.get(stage, []),
                       "exit_code": 0 if stage in commands else None, "source_hash": source_tree_hash(ROOT),
                       "evidence_paths": {"S0": ["BASELINE.json", "WRITER.json"], "S1": ["NETWORK_PATH_DIAGNOSIS.json", "s1-completion/S1_RESULT.json"],
                         "S2": ["PROFILE_MATRIX.yaml"], "S3": ["COMPATIBILITY_AND_EFFORT_REPORT.md"], "S4": ["BENCHMARK_TASKSET_FROZEN.json", "SCORECARD_ALL_MODELS.csv"],
                         "S5": ["FAILOVER_NEGATIVE_TESTS.xml", "PROVIDER_REGRESSION_R2.xml", "S1_RESUME_NO_SEND.txt"], "S6": ["ROUND_REPORT.md", "NEXT_ACTIONS.md"]}[stage],
                       "counts": {"new_completion": 1, "successful_completion": 0} if stage == "S1" else regression if stage == "S5" else {},
                       "limitations": limitation})
    write(out / "STAGES.json", stages)
    runtime, head = source_tree_hash(ROOT), subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    write(out / "SUMMARY.json", {"status": "BLOCKED_AUTH_PERMISSION", "HEAD_at_report_generation": head,
        "runtime_sha256": runtime, "PROVIDER_RECOVERED": "NO", "CATALOG_VERIFIED": present,
        "catalog_definition": "Exact ID present in fresh public catalog, NOT key authorization", "CONFIG_VERIFIED": 0,
        "STABLE_OBSERVED": 0, "PROVISIONAL": 0, "FIRST_MACHINE_QUALIFIED": "BLOCKED", "Gold_PI": "HUMAN_REQUIRED",
        "regression": regression, "focused_negative_tests_included_in_full_regression": negative,
        "source_file": str(Path(__file__).relative_to(ROOT)), "source_sha256": sha(Path(__file__)),
        "generated_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"status": "BLOCKED_AUTH_PERMISSION", "catalog_present": present, "regression": regression, "protected": len(baseline["protected_files"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build(parser.parse_args().out.resolve())
