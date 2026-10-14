"""Replay integrity audit over the authoritative formal runs (G11 evidence).

For every terminal unit in the 18 formal runs this audit re-derives from the
persisted replay bundles:

- immutable request hashes (request_sha256 == recomputed canonical hash);
- oracle isolation (no oracle_payload reference in any model input);
- simulation provenance (T361-T363: SYNTHETIC_HUMAN records present, runtime
  2.1.0, synthetic-human manifest metadata, SIMULATION_ONLY eligibility);
- terminal-state discipline (COMPLETED / INVALID_MODEL_OUTPUT only).

Usage: python scripts/final_replay_audit.py [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.frozen_versions import FROZEN_VERSIONS  # noqa: E402
from ioabench.hashing import canonical_sha256  # noqa: E402

MODEL = "deepseek-v4.1-flash"


def audit_suite(suite: str, version: str) -> dict:
    run_dir = ROOT / "data" / "runs" / f"{MODEL}-{suite}-{version}-formal"
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    audited = 0
    simulation = suite in {"T361", "T362", "T363"}
    sh_records_seen = 0
    for case_id, value in results.items():
        status = value.get("status")
        if status not in {"COMPLETED", "INVALID_MODEL_OUTPUT"}:
            failures.append(f"{case_id}: non-terminal status {status}")
            continue
        replay = value.get("replay")
        if not replay:
            if status == "COMPLETED":
                failures.append(f"{case_id}: completed unit without replay bundle")
            continue
        audited += 1
        manifest = (replay.get("scenario") or {}).get("manifest") or {}
        for record in replay.get("model_records", []):
            if canonical_sha256(record["request"]) != record.get("request_sha256"):
                failures.append(f"{case_id}/{record.get('record_id')}: request hash mismatch")
            if "oracle_payload" in json.dumps(record["request"].get("messages", [])):
                failures.append(f"{case_id}/{record.get('record_id')}: oracle reference in model input")
        if simulation:
            sh_records = [r for r in replay.get("model_records", [])
                          if (r["request"].get("role_metadata") or {}).get("role") == "SYNTHETIC_HUMAN"]
            sh_records_seen += len(sh_records)
            if status == "COMPLETED" and not sh_records:
                failures.append(f"{case_id}: simulation case without SYNTHETIC_HUMAN records")
            if not str(manifest.get("runtime_version", "")).endswith("-agency-2.1.0"):
                failures.append(f"{case_id}: simulation runtime version {manifest.get('runtime_version')}")
            sh_meta = manifest.get("synthetic_human") or {}
            if not sh_meta.get("simulation_only") or not sh_meta.get("persona_id"):
                failures.append(f"{case_id}: synthetic-human manifest metadata missing")
            agents = replay.get("agents") or []
            persona_agent = next((a for a in agents if a.get("agent_id") == "synthetic-persona"), None)
            if not persona_agent or persona_agent.get("model_role") != "SYNTHETIC_HUMAN":
                failures.append(f"{case_id}: synthetic-persona agent entry missing")
            if value.get("eligibility") not in {"SIMULATION_ONLY", "INVALID_MODEL_OUTPUT"}:
                failures.append(f"{case_id}: eligibility {value.get('eligibility')} not simulation-labelled")
    return {"suite": suite, "dataset_version": version, "units": len(results),
            "audited_with_replay": audited, "synthetic_human_records": sh_records_seen,
            "failures": failures, "pass": not failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    suites = []
    for suite, version in FROZEN_VERSIONS.items():
        suites.append(audit_suite(suite, version))
    report = {"artifact": "REPLAY_AUDIT_V3",
              "audited_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "tested_model": MODEL,
              "suites": suites,
              "total_failures": sum(len(s["failures"]) for s in suites),
              "pass": all(s["pass"] for s in suites)}
    print(json.dumps({s["suite"]: {"units": s["units"], "sh_records": s["synthetic_human_records"],
                                    "pass": s["pass"]} for s in suites}, indent=0))
    print("total failures:", report["total_failures"], "| pass:", report["pass"])
    if args.write:
        out = ROOT / "artifacts" / "gates" / "REPLAY_AUDIT_V3.json"
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written:", out)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
