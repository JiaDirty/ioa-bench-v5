"""Pinned engineering batches over supplied cases; no data generation or formal campaign."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from ioabench.errors import ProviderPermanentError
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter
from ioabench.v5.core.case import Case, SUITES, case_from_dict, pair_diff_violations
from ioabench.v5.core.engine import ActionRecord
from ioabench.v5.core.monitor import evaluate_timing, ledger_integrity, message_flow
from ioabench.v5.core.outcome import derive_outcome
from ioabench.v5.dynamic import registry
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.runner import run_case
from ioabench.v5.suites import load
from ioabench.v5.scenario_profiles import validate_profile

VERSION = "v5-engineering-evaluation-1.1.0"
CODE_ROOT = Path(__file__).resolve().parents[3]


def safe_id(value: str) -> str:
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}", value)
            or value.endswith(".") or value.split(".")[0].upper() in
            {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
        raise ValueError(f"unsafe run/case identifier: {value!r}")
    return value


def atomic_json(path: Path, value: Any) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, path)


@contextmanager
def writer_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".writer.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def read_cases(path: Path, suites: list[str] | None = None) -> list[Case]:
    selected = set(suites or SUITES)
    if not selected <= set(SUITES) | set(registry.implemented()):
        raise ValueError("unknown selected suite")
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = case_from_dict(json.loads(line), allow_dynamic=True)
        safe_id(case.case_id)
        if case.suite_id in selected or case.suite_id.split("-")[0] in selected:
            cases.append(case)
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("supplied cases are empty or contain duplicate case IDs")
    pairs: dict[tuple[str, str], dict[str, Case]] = {}
    for case in cases:
        arms = pairs.setdefault((case.suite_id, case.pair_id), {})
        if case.arm in arms:
            raise ValueError(f"duplicate pair arm: {case.pair_id}/{case.arm}")
        arms[case.arm] = case
    for key, arms in pairs.items():
        if set(arms) != {"CONTROL", "RISK"}:
            raise ValueError(f"incomplete supplied pair: {key}")
        control, risk = arms["CONTROL"], arms["RISK"]
        if (control.family_id != risk.family_id or control.subtype != risk.subtype
                or control.difficulty != risk.difficulty):
            raise ValueError(f"pair metadata mismatch: {key}")
        if pair_diff_violations(control, risk):
            raise ValueError(f"undeclared paired-world differences: {key}")
        if control.suite_id not in SUITES:
            adapter = registry.get_adapter(control.suite_id)
            if adapter.fine_arm_delta(control, risk):
                raise ValueError(f"invalid dynamic mechanism direction: {key}")
    return cases


def adapter_for(case: Case):
    return load(case.suite_id) if case.suite_id in SUITES else registry.get_adapter(case.suite_id)


def execute_case(root: Path, case: Case, port: Any, profile: ModelProfile,
                 run_id: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    adapter = adapter_for(case)
    validate_profile(case)
    if case.suite_id not in SUITES:
        return run_dynamic_case(root, case, adapter, port, profile, run_id=run_id, parameters=parameters)
    auxiliary = adapter.reference_auxiliary() if hasattr(adapter, "reference_auxiliary") else None
    result = asyncio.run(run_case(root, case, port, profile, run_id=run_id,
                                  parameters=parameters, auxiliary=auxiliary))
    if "trace" in result:
        from types import SimpleNamespace
        trace = SimpleNamespace(actions=[ActionRecord(**a) for a in result["trace"]["actions"]],
                                events=result["trace"]["events"])
        flow = message_flow(trace)
        integrity = ledger_integrity(trace)
        timing = evaluate_timing(trace, list(getattr(adapter, "TIMING_RULES", ())))
        result["monitor_report"] = {"monitor_version": "v5-engineering-batch-monitor-1.0.0",
            "ledger_integrity": integrity, "timing_properties": timing,
            "message_flow": {"paired": flow["paired"], "undelivered_enqueues": len(flow["undelivered_enqueues"])}}
        reasons = []
        if not integrity["passed"]:
            reasons.append("LEDGER_INTEGRITY_FAILED")
        if timing.get("indeterminate"):
            reasons.append("TIMING_INDETERMINATE")
        result["ineligibility_reasons"] = reasons
        result["scientifically_eligible"] = not reasons and result["outcome"]["eligibility"] == "ELIGIBLE"
    else:
        result["monitor_report"] = {"status": "NOT_AVAILABLE", "reason": result["status"],
            "ledger_integrity": {"passed": None}, "timing_properties": {"passed": None},
            "message_flow": {"paired": None, "undelivered_enqueues": None}}
    return result


class IdentityGuard:
    """Refuse a different response identity before any of its proposed actions execute."""

    def __init__(self, port: Any, expected: Mapping[str, Any]):
        self.port, self.expected = port, dict(expected)

    async def generate(self, profile, request):
        response = await self.port.generate(profile, request)
        metadata = dict(response.provider_metadata)
        observed = {"body_model": str(metadata.get("model", "")),
                    "gateway_model": str(metadata.get("transport_metadata", {}).get("x-aihubmix-model", ""))}
        allowed_bodies = self.expected.get("body_aliases", [self.expected["body_model"]])
        if (observed["gateway_model"] != self.expected["gateway_model"]
                or observed["body_model"] not in allowed_bodies):
            snapshot = {"messages": list(request.messages), "tools": list(request.tools),
                        "parameters": dict(request.parameters), "role_metadata": dict(request.role_metadata)}
            journal = AttemptJournal.current()
            if journal is not None:
                journal.record({"agent_id": request.role_metadata.get("agent_id"), "request": snapshot,
                                "request_sha256": canonical_sha256(snapshot), "response": asdict(response),
                                "identity_expected": self.expected, "identity_observed": observed,
                                "identity_rejected": True})
            raise ProviderPermanentError("MODEL_IDENTITY_MISMATCH: " + json.dumps(observed, sort_keys=True))
        return response


def _append(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _jsonl_prefix(path: Path) -> tuple[list[dict[str, Any]], bool]:
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    entries = []
    truncated = False
    for number, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if number != len(lines) - 1 or line.endswith(b"\n"):
                raise ValueError(f"corrupt complete JSONL entry: {path.name}:{number + 1}")
            truncated = True
    return entries, truncated


def _result_segments(directory: Path) -> list[Path]:
    return ([directory / "results.jsonl"] if (directory / "results.jsonl").exists() else []) + sorted(
        directory.glob("results-*.jsonl"), key=lambda p: int(p.stem.split("-")[-1]))


def read_results(directory: Path) -> list[dict[str, Any]]:
    return [row for path in _result_segments(directory) for row in _jsonl_prefix(path)[0]]


def _result_append_path(directory: Path) -> Path:
    segments = _result_segments(directory)
    if not segments:
        return directory / "results.jsonl"
    latest = segments[-1]
    if latest.read_bytes().endswith(b"\n"):
        return latest
    # Keep interrupted writes intact; a new append segment cannot merge with their tail.
    return directory / f"results-{len(segments) + 1}.jsonl"


def _interrupted(root: Path, run_id: str, case: Case) -> dict[str, Any] | None:
    directory = root / "data" / "runs" / run_id / "attempts" / case.case_id
    journals = sorted(directory.glob("attempt-*.jsonl"), key=lambda p: int(p.stem.split("-")[-1]))
    if not journals:
        return None
    path = journals[-1]
    entries, truncated = _jsonl_prefix(path)
    if (not entries and not truncated) or (entries and any(entries[0].get(k) != v for k, v in
            {"kind": "attempt", "run_id": run_id, "suite_id": case.suite_id, "case_id": case.case_id}.items())):
        raise ValueError("interrupted journal identity mismatch")
    for entry in entries[1:]:
        if entry.get("kind") != "model_record" or canonical_sha256(entry["record"]) != entry.get("record_sha256"):
            raise ValueError("interrupted journal record hash mismatch")
    records = sum(entry.get("kind") == "model_record" for entry in entries)
    if not records and not truncated:
        return None
    return {"run_id": run_id, "case_id": case.case_id, "case_sha256": case.content_sha256(),
            "suite_id": case.suite_id, "pair_id": case.pair_id, "family_id": case.family_id,
            "arm": case.arm, "simulation_only": case.simulation_only, "status": "INFRA_INTERRUPTED",
            "error": "Process stopped after recorded model behavior; original attempt retained, not re-executed.",
            "model_calls": records, "scientifically_eligible": False,
            "ineligibility_reasons": ["PROCESS_INTERRUPTED"] + (["TRUNCATED_JOURNAL"] if truncated else []),
            "outcome": derive_outcome("INFRA_INTERRUPTED", {}, None),
            "attempt_journal": {"path": path.relative_to(root).as_posix(),
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}


def run_batch(root: Path, cases_path: Path, *, run_id: str, profile: ModelProfile,
              port: Any = None, parameters: Mapping[str, Any] | None = None,
              reference_policy: str | None = None, suites: list[str] | None = None,
              expected_identity: Mapping[str, Any] | None = None,
              resume: bool = False, max_attempts: int = 2,
              required_model_id: str = "deepseek-v4.1-flash") -> dict[str, Any]:
    from ioabench.v5.reporting import build_report

    safe_id(run_id)
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be 1..3")
    if reference_policy is None and (port is None or not expected_identity or profile.model_id != required_model_id):
        raise ValueError(f"online engineering runs require {required_model_id} and an exact preflight identity")
    cases = read_cases(cases_path, suites)
    for case in cases:
        validate_profile(case)
    parameters = dict(parameters or {})
    directory = root / "artifacts" / "v5" / "evaluations" / run_id
    manifest = {"version": VERSION, "run_id": run_id, "source_sha256": source_tree_hash(CODE_ROOT),
                "evidence_class": "ENGINEERING_REFERENCE" if reference_policy else "ENGINEERING_SMOKE",
                "profile": asdict(profile), "parameters": parameters, "reference_policy": reference_policy,
                "expected_identity": dict(expected_identity or {}), "max_attempts": max_attempts,
                "cases": [{"case_id": c.case_id, "case_sha256": c.content_sha256(), "suite_id": c.suite_id,
                           "pair_id": c.pair_id, "family_id": c.family_id, "arm": c.arm,
                           "scenario_profile": c.provenance.get("required_scenario_profile")} for c in cases]}
    with writer_lock(directory):
        pinned = directory / "manifest.json"
        if pinned.exists():
            if not resume:
                raise FileExistsError("run exists; use --resume with the identical inputs and configuration")
            if json.loads(pinned.read_text(encoding="utf-8")) != manifest:
                raise ValueError("pinned run manifest mismatch; inputs/model/parameters/source changed")
        else:
            if (root / "data" / "runs" / run_id).exists():
                raise FileExistsError("run ID already has evidence outside this pinned engineering run")
            if resume and not (directory / "cases.jsonl").exists():
                raise FileNotFoundError("cannot resume a run without its manifest or uncommitted input snapshot")
            snapshot = "".join(json.dumps(c.as_dict(), ensure_ascii=False, sort_keys=True) + "\n" for c in cases)
            if (directory / "cases.jsonl").exists():
                if (directory / "cases.jsonl").read_text(encoding="utf-8") != snapshot:
                    raise ValueError("uncommitted case snapshot differs from supplied inputs")
            else:
                _atomic_text(directory / "cases.jsonl", snapshot)
            atomic_json(pinned, manifest)
        saved = [case_from_dict(json.loads(line), allow_dynamic=True)
                 for line in (directory / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if [c.content_sha256() for c in saved] != [c.content_sha256() for c in cases]:
            raise ValueError("saved run inputs differ from supplied/pinned cases")
        rows = read_results(directory)
        results_path = _result_append_path(directory)
        hashes = {c.case_id: c.content_sha256() for c in cases}
        for row in rows:
            if hashes.get(row.get("case_id")) != row.get("case_sha256"):
                raise ValueError("existing result is not bound to a supplied case")
        done = {row["case_id"] for row in rows if row["status"] != "RETRYABLE_INFRA_FAILURE"}
        if len(done) != sum(row["status"] != "RETRYABLE_INFRA_FAILURE" for row in rows):
            raise ValueError("duplicate terminal result; manual investigation required")
        guarded = IdentityGuard(port, expected_identity) if reference_policy is None else None
        for case in cases:
            if case.case_id in done:
                continue
            attempts = max(sum(row["case_id"] == case.case_id for row in rows), attempt_counter(root, run_id, case.case_id) - 1)
            recovered = _interrupted(root, run_id, case)
            if recovered:
                recovered.update(model_id=profile.model_id, evidence_class=manifest["evidence_class"])
                _append(results_path, recovered)
                rows.append(recovered)
                done.add(case.case_id)
                continue
            while attempts < max_attempts:
                attempts += 1
                atomic_json(directory / "checkpoint.json", {"status": "RUNNING", "current_case": case.case_id,
                            "completed": len(done), "scheduled": len(cases), "attempt": attempts})
                try:
                    selected_port = adapter_for(case).policies()[reference_policy] if reference_policy else guarded
                    result = execute_case(root, case, selected_port, profile, run_id, parameters)
                except Exception as exc:
                    result = _interrupted(root, run_id, case) or {
                        "run_id": run_id, "case_id": case.case_id, "case_sha256": case.content_sha256(),
                        "suite_id": case.suite_id, "pair_id": case.pair_id, "family_id": case.family_id,
                        "arm": case.arm, "simulation_only": case.simulation_only, "model_id": profile.model_id,
                        "model_calls": 0}
                    result.update(status="ENGINEERING_ERROR", error=f"{type(exc).__name__}: {exc}",
                                  model_id=profile.model_id,
                                  outcome=derive_outcome("ENGINEERING_ERROR", {}, None),
                                  ineligibility_reasons=["ENGINEERING_ERROR"])
                result["evidence_class"] = manifest["evidence_class"]
                if result["status"] != "COMPLETED":
                    result["scientifically_eligible"] = False
                elif "scientifically_eligible" not in result:
                    result["scientifically_eligible"] = result["outcome"]["eligibility"] == "ELIGIBLE"
                if "MODEL_IDENTITY_MISMATCH" in str(result.get("error", "")):
                    result["ineligibility_reasons"] = ["MODEL_IDENTITY_MISMATCH"]
                _append(results_path, result)
                rows.append(result)
                if result["status"] != "RETRYABLE_INFRA_FAILURE":
                    done.add(case.case_id)
                    break
        report = build_report(rows, manifest)
        paths = publish_report(report, directory)
        atomic_json(directory / "checkpoint.json", {"status": "FINISHED" if len(done) == len(cases) else "FINISHED_WITH_INFRA_FAILURES",
                    "completed": len(done), "scheduled": len(cases), "retryable_unfinished": len(cases) - len(done),
                    "report": paths["html"].relative_to(root).as_posix()})
        return report


def publish_report(report: dict[str, Any], directory: Path) -> dict[str, Path]:
    from ioabench.v5.reporting import write_report

    reports = directory / "reports"
    number = 1
    while (reports / f"report-{number}").exists():
        number += 1
    return write_report(report, reports / f"report-{number}")
