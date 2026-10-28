"""Verify retained factory evidence, protected history and zero-call panel replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.factory import validate_saved_result
from ioabench.v5.evaluation import atomic_json
from ioabench.v5.replay import replay_case
from calibrate_factory_candidates import (check_panel_identity, planned_panel,
    verify_retained_attempts, verify_stopped_outputs)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def immutable_json(path, value):
    if path.exists() and read(path) != value:
        raise ValueError(f"immutable verification evidence changed: {path}")
    if not path.exists():
        atomic_json(path, value)


def protected_history(root, baseline):
    changed, missing = [], []
    for name, expected in baseline["protected_files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("protected inventory escapes workspace")
        if not path.is_file():
            missing.append(name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(name)
    return {"status": "PASS" if not changed and not missing else "FAIL",
            "checked": len(baseline["protected_files"]), "changed": changed, "missing": missing}


def trial_evidence(directory):
    manifest = read(directory / "SOURCE_MANIFEST.json")
    archive = directory / "source.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("factory source archive digest changed")
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None or set(zipped.namelist()) != set(manifest["files"]):
            raise ValueError("factory source archive CRC or membership failed")
        if any(hashlib.sha256(zipped.read(name)).hexdigest() != digest for name, digest in manifest["files"].items()):
            raise ValueError("factory source archive member digest changed")
    rows = []
    for path in sorted(directory.glob("candidate-*/RESULT.json")):
        result = read(path)
        validate_saved_result(path.parent, result)
        rows.append({"candidate": path.parent.name, "status": result["status"],
                     "failed_stage": result.get("failed_stage"), "bound_files": len(result["evidence_sha256"])})
    return {"run_id": directory.name, "source_archive": "PASS", "candidates": rows}


def replay_panel(directory):
    directory = Path(directory).resolve()
    failure = {"status": "FAIL", "provider_calls": 0, "rows": []}
    try:
        contract, expected = planned_panel(directory)
        stopped = verify_stopped_outputs(directory) if (directory / "STOP_REPORT.json").exists() else None
        results = read(directory / "RESULTS.json")
        identities = [row["run_id"] for row in results]
        if len(identities) != len(expected) or len(set(identities)) != len(identities) or set(identities) != set(expected):
            raise ValueError("calibration rows differ from the unique fixed panel")
        if any("trace" in row for row in results) and source_tree_hash(ROOT) != contract["runtime_source_sha256"]:
            raise ValueError("strict replay requires the panel's recorded runtime source")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return {**failure, "error": str(exc)}
    reports = []
    for row in results:
        ident = row["run_id"]
        case, model = expected[ident]
        report = {"run_id": ident, "episode_status": row["status"], "replay": "NOT_RUN"}
        try:
            check_panel_identity(row, case, model, ident)
            original = directory / "episodes" / ident / "RESULT.json"
            if original.exists():
                if read(original) != row:
                    raise ValueError("aggregate row differs from original retained result")
            elif not stopped or not row.get("settled_offline") or "trace" in row:
                raise ValueError("panel row has no retained result or offline stop settlement")
            evidence = verify_retained_attempts(directory, row, case, model)
            if stopped and stopped["attempt_evidence_checks"].get(ident) != evidence:
                raise ValueError("stopped panel attempt verification changed")
            report["attempt_evidence"] = evidence
            if "trace" not in row:
                report.update(status="NOT_RUN" if row["status"] == "NOT_RUN" else "INTERRUPTION_EVIDENCE_VALID",
                              passed=True)
            else:
                run = directory / "replay/artifacts/v5/evaluations" / ident
                immutable_json(run / "manifest.json", {"source_sha256": contract["runtime_source_sha256"],
                    "profile": model["profile"], "parameters": model["parameters"],
                    "cases": [{"case_id": case.case_id, "case_sha256": case.content_sha256()}]})
                for name, value in (("cases.jsonl", case.as_dict()), ("results.jsonl", row)):
                    content = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
                    path = run / name
                    if path.exists() and path.read_text(encoding="utf-8") != content:
                        raise ValueError("replay input differs from retained panel evidence")
                    if not path.exists():
                        path.write_text(content, encoding="utf-8", newline="\n")
                replay = replay_case(directory / "replay", ident, case.case_id)
                report.update(replay="PASS" if replay["passed"] else "FAIL", strict_replay=replay,
                              status="STRICT_REPLAY_PASS" if replay["passed"] else "STRICT_REPLAY_FAIL",
                              passed=replay["passed"])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            report.update(status="FAIL", passed=False, error=str(exc))
        reports.append(report)
    return {"status": "PASS" if all(row["passed"] for row in reports) else "FAIL",
            "panel_status": "STOPPED" if stopped else "RETAINED_RESULTS", "planned_episodes": len(expected),
            "episodes": len(reports), "strict_replay_passed": sum(row["replay"] == "PASS" for row in reports),
            "strict_replay_failed": sum(row["replay"] == "FAIL" for row in reports),
            "interruption_evidence_valid": sum(row["status"] == "INTERRUPTION_EVIDENCE_VALID" for row in reports),
            "not_run_episodes": sum(row["status"] == "NOT_RUN" for row in reports),
            "replay_not_run": sum(row["replay"] == "NOT_RUN" for row in reports),
            "provider_calls": 0, "formal_accepted": False, "rows": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--trial", type=Path, action="append", default=[])
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"source_sha256": source_tree_hash(ROOT), "protected_history": protected_history(ROOT, read(args.baseline)),
              "trials": [trial_evidence(path) for path in args.trial],
              "panel_replay": replay_panel(args.calibration) if args.calibration else {"status": "NOT_RUN"},
              "provider_calls": 0, "formal_accepted": False}
    immutable_json(args.output, report)
    print(json.dumps({"output": str(args.output), "protected_history": report["protected_history"],
                      "panel_replay": {key: value for key, value in report["panel_replay"].items() if key != "rows"}}, ensure_ascii=False))
    return 0 if report["protected_history"]["status"] == "PASS" and report["panel_replay"]["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
