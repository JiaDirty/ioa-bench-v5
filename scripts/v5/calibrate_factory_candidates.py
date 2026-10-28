"""Exploratory auxiliary panel on source/family-bound development pairs, never formal SUT."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryRouter, qualified_contracts, WIRE_REQUEST_FORMAT
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.core.case import case_from_dict, SUITES
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.evaluation import atomic_json, safe_id
from ioabench.v5.stats import wilson
from ioabench.v5.core.outcome import derive_outcome
from routed_t321_data_factory_s1 import _load_api_key, _lock


def panel_summary(results):
    groups = {}
    for suite in sorted({row["suite_id"] for row in results}):
        rows = [row for row in results if row["suite_id"] == suite]
        eligible = [row for row in rows if row.get("scientifically_eligible")]
        utility = sum(bool((row.get("score") or {}).get("utility")) for row in eligible)
        safe = sum((row.get("score") or {}).get("safety") == "SAFE" for row in eligible)
        groups[suite] = {"episodes": len(rows), "eligible": len(eligible), "utility_success": utility,
            "utility_wilson_95": list(wilson(utility, len(eligible))) if eligible else None,
            "safe_behavior": safe, "safety_wilson_95": list(wilson(safe, len(eligible))) if eligible else None,
            "outcomes": dict(Counter((row.get("outcome") or {}).get("legacy_class", "UNKNOWN") for row in rows)),
            "raw_safety": dict(Counter((row.get("score") or {}).get("safety", "NOT_SCORED") for row in rows)),
            "statuses": dict(Counter(row["status"] for row in rows)),
            "model_calls": sum(row.get("model_calls", 0) for row in rows),
            "verification_actions": sum(action["tool"].startswith(("check_", "verify_", "query_", "read_", "view_"))
                for row in rows for action in row.get("trace", {}).get("actions", [])),
            "by_model_and_arm": {model + "/" + arm: [{"status": row["status"], "score": row.get("score"),
                "outcome": row.get("outcome"), "model_calls": row.get("model_calls"), "exposure": row.get("exposure")}
                for row in rows if row["model_id"] == model and row["arm"] == arm]
                for model in sorted({row["model_id"] for row in rows}) for arm in ("CONTROL", "RISK")},
            "difficulty_empirical": "MEASURED_EXPLORATORY_UNCALIBRATED_LABEL",
            "label_reason": "No approved numerical label threshold; small panel intervals and family dependence retained."}
    return groups


class PanelPort:
    def __init__(self, router):
        self.router, self.counter = router, 0

    async def generate(self, profile, request):
        self.counter += 1
        return await self.router.invoke("CALIBRATOR", f"call-{self.counter:03d}", request)


def planned_panel(output):
    output = Path(output)
    contract = json.loads((output / "CALIBRATION_CONTRACT.json").read_text(encoding="utf-8"))
    cases = [case_from_dict(raw, allow_dynamic=True)
             for raw in json.loads((output / "PAIRS.json").read_text(encoding="utf-8"))]
    if [case.content_sha256() for case in cases] != contract["selected_case_sha256"]:
        raise ValueError("panel cases differ from the fixed selection")
    if not cases or not contract["models"] or contract["repetitions"] not in (1, 2, 3):
        raise ValueError("invalid fixed panel selection")
    expected = {}
    for model in contract["models"]:
        for repetition in range(1, contract["repetitions"] + 1):
            for case in cases:
                ident = f"{model['profile']['model_id']}-r{repetition}-{case.suite_id}-{case.arm.lower()}"
                safe_id(ident)
                if ident in expected:
                    raise ValueError("duplicate fixed panel episode identity")
                expected[ident] = (case, model)
    return contract, expected


def check_panel_identity(row, case, model, ident):
    expected = {"run_id": ident, "case_sha256": case.content_sha256(), "case_id": case.case_id,
                "suite_id": case.suite_id, "arm": case.arm, "pair_id": case.pair_id,
                "family_id": case.family_id, "model_id": model["profile"]["model_id"]}
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError("retained panel case/model identity changed")


def verify_retained_attempts(output, row, case, model):
    """Validate durable evidence only; incomplete episodes are never executed or scored."""
    output = Path(output).resolve()
    check_panel_identity(row, case, model, row["run_id"])
    target = output / "episodes" / row["run_id"]
    ledger = target / "model_io/AIHUBMIX_ATTEMPTS.jsonl"
    journals = output / "replay/data/runs" / row["run_id"] / "attempts" / case.case_id
    incomplete = "trace" not in row
    if incomplete and (row["status"] not in {"NOT_RUN", "INFRA_INTERRUPTED", "RETRYABLE_INFRA_FAILURE",
            "INTERRUPTED_WITH_PENDING_REQUEST"} or row.get("score") is not None
            or row.get("scientifically_eligible") is not False
            or row.get("outcome") != derive_outcome(row["status"], {}, None)):
        raise ValueError("incomplete panel row contains an invalid status or scored behavioral result")
    if row["status"] == "NOT_RUN":
        if ledger.exists() or list(journals.glob("attempt-*.jsonl")):
            raise ValueError("NOT_RUN episode contains an actual request or attempt")
        if not incomplete or row.get("attempt_journal") or row.get("model_calls") != 0:
            raise ValueError("NOT_RUN episode contains fabricated execution evidence")
        return {"status": "NOT_RUN", "journal_records": 0, "request_attempts": 0}
    pointer = row.get("attempt_journal") or {}
    path = (output / "replay" / pointer.get("path", "")).resolve()
    if not path.is_relative_to((output / "replay").resolve()) or not path.is_file():
        raise ValueError("missing or escaping attempt journal")
    if list(journals.glob("attempt-*.jsonl")) != [path]:
        raise ValueError("fixed panel contains an unbound or repeated episode attempt")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != pointer.get("sha256"):
        raise ValueError("attempt journal hash mismatch")
    entries = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
    header = {"kind": "attempt", "run_id": row["run_id"], "suite_id": case.suite_id,
              "case_id": case.case_id, "attempt_no": row["attempt_no"]}
    if not entries or entries[0] != header:
        raise ValueError("attempt journal identity mismatch")
    records = []
    for entry in entries[1:]:
        record = entry.get("record", {})
        if (entry.get("kind") != "model_record" or canonical_sha256(record) != entry.get("record_sha256")
                or canonical_sha256(record.get("request")) != record.get("request_sha256")):
            raise ValueError("attempt journal record/request hash mismatch")
        records.append(record)
    if (len(records) != row.get("model_calls") or (row["status"] == "INFRA_INTERRUPTED" and not records)
            or (row["status"] == "RETRYABLE_INFRA_FAILURE" and records)):
        raise ValueError("interrupted model-record denominator changed")
    if not ledger.is_file():
        raise ValueError("panel router ledger is missing")
    ledger_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()
    AuxiliaryRouter.verify_ledger(SimpleNamespace(directory=ledger.parent))
    events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    starts, finishes, responses, per_request = {}, {}, [], Counter()
    unresolved_seen = False
    for event in events:
        kind = event.get("event")
        if kind == "REQUEST_STARTED":
            if unresolved_seen or len(starts) != len(finishes) or event["attempt_id"] in starts:
                raise ValueError("request was repeated after an unresolved or duplicate attempt")
            if (event.get("requested_model_id") != row["model_id"] or event.get("role") != "CALIBRATOR"
                    or event.get("actual_parameters") != model["parameters"]):
                raise ValueError("router request differs from the fixed panel model/parameters")
            starts[event["attempt_id"]] = event
            per_request[event["request_id"]] += 1
            safe_id(event["request_id"])
            binding = json.loads((ledger.parent / event["request_id"] / "REQUEST_BINDING.json").read_text(encoding="utf-8"))
            bound = binding["binding"]
            wire = {**bound["request"], "parameters": model["parameters"],
                    "role_metadata": {**bound["request"].get("role_metadata", {}),
                                      "role": "CALIBRATOR", "attempt_id": event["attempt_id"]}}
            wire_format = event.get("wire_request_format")
            if wire_format == WIRE_REQUEST_FORMAT:
                evidence = Path(event["stream_evidence_path"])
                if (evidence.parent.name != event["request_id"]
                        or evidence.name != f"attempt-{per_request[event['request_id']]:03d}.sse"):
                    raise ValueError("stream evidence path does not belong to its request attempt")
                wire["role_metadata"]["stream_evidence_path"] = event["stream_evidence_path"]
            elif wire_format is not None:
                raise ValueError("unsupported router wire-request format")
            if (canonical_sha256(bound) != binding["sha256"] or bound["role"] != "CALIBRATOR"
                    or bound["contracts"] != [model] or canonical_sha256(wire) != event["request_sha256"]):
                raise ValueError("router request binding/model/wire hash changed")
        elif kind == "REQUEST_FINISHED":
            start = starts.get(event["attempt_id"])
            if start is None or event["attempt_id"] in finishes or any(event.get(key) != start.get(key)
                    for key in ("request_id", "requested_model_id", "role", "request_sha256", "actual_parameters",
                                "wire_request_format", "stream_evidence_path")):
                raise ValueError("router completion differs from its unique request")
            finishes[event["attempt_id"]] = event
            if event.get("status") == "SUCCEEDED":
                if event.get("served_model_id") != row["model_id"]:
                    raise ValueError("successful router response has a different served model")
                responses.append(event)
            elif event.get("status") == "REQUEST_UNRESOLVED":
                unresolved_seen = True
            elif event.get("status") != "FAILED":
                raise ValueError("unknown router terminal status")
    budget = suite_spec(case.suite_id).scenario_factory().budget(case.world).max_model_calls
    if not starts or max(per_request.values()) > 3 or len(per_request) > budget or len(records) > budget:
        raise ValueError("panel request count is not bounded by the retained execution budget")
    if len(responses) < len(records) or (not incomplete and len(responses) != len(records)):
        raise ValueError("router responses and journal records differ")
    for record, event in zip(records, responses):
        response = event["response"]
        if any(canonical_sha256(value) != canonical_sha256(response.get(key))
               for key, value in record["response"].items() if key != "elapsed_seconds"):
            raise ValueError("router response differs from journal evidence")
        binding = json.loads((ledger.parent / event["request_id"] / "REQUEST_BINDING.json").read_text(encoding="utf-8"))
        if (canonical_sha256(binding["binding"]) != binding["sha256"]
                or canonical_sha256(binding["binding"]["request"]) != record["request_sha256"]):
            raise ValueError("router request binding differs from journal evidence")
    if incomplete and len(starts) == len(responses) == len(records):
        raise ValueError("interruption lacks a retained failed or pending provider request")
    if hashlib.sha256(ledger.read_bytes()).hexdigest() != ledger_hash:
        raise ValueError("router ledger changed during validation")
    return {"status": "VERIFIED", "journal_records": len(records), "request_attempts": len(starts),
            "failed_attempts": sum(event["status"] == "FAILED" for event in finishes.values()),
            "unresolved_attempts": sum(event["status"] == "REQUEST_UNRESOLVED" for event in finishes.values()),
            "pending_attempts": len(starts) - len(finishes), "ledger_sha256": ledger_hash,
            "journal_sha256": pointer["sha256"]}


def retained_panel_files(output):
    files = [output / name for name in ("CALIBRATION_CONTRACT.json", "PAIRS.json", "PROGRESS.json") if (output / name).exists()]
    files += [path for root in (output / "episodes", output / "replay/data/runs")
              for path in root.rglob("*") if path.is_file()]
    return {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def verify_stopped_outputs(output):
    stopped = json.loads((output / "STOP_REPORT.json").read_text(encoding="utf-8"))
    contract = json.loads((output / "CALIBRATION_CONTRACT.json").read_text(encoding="utf-8"))
    if (stopped["status"] != "STOPPED_OFFLINE_SETTLED" or stopped["provider_calls"] != 0
            or stopped["original_runtime_source_sha256"] != contract["runtime_source_sha256"]
            or stopped["original_script_sha256"] != contract["script_sha256"]
            or stopped["evidence_sha256"] != retained_panel_files(output)):
        raise ValueError("stopped panel retained evidence or original contract changed")
    for name, digest in stopped["settled_outputs_sha256"].items():
        if name not in {"RESULTS.json", "CALIBRATION_REPORT.json"} or hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
            raise ValueError("stopped panel settled output changed: " + name)
    if set(stopped["settled_outputs_sha256"]) != {"RESULTS.json", "CALIBRATION_REPORT.json"}:
        raise ValueError("stopped panel output binding is incomplete")
    report = json.loads((output / "CALIBRATION_REPORT.json").read_text(encoding="utf-8"))
    if not stopped["reason"].strip() or stopped["reason"] != report["stop_reason"]:
        raise ValueError("stopped panel reason differs from its bound report")
    return stopped


def verify_terminal_panel(output):
    """Check retained terminal evidence before returning it without opening a Provider."""
    contract, expected = planned_panel(output)
    stopped = (output / "STOP_REPORT.json").exists()
    if stopped:
        binding = verify_stopped_outputs(output)
    else:
        binding = json.loads((output / "COMPLETION_REPORT.json").read_text(encoding="utf-8"))
        if (binding["status"] != "COMPLETED_EVIDENCE_BOUND"
                or binding["evidence_sha256"] != retained_panel_files(output)):
            raise ValueError("completed panel retained evidence changed")
        for name, digest in binding["settled_outputs_sha256"].items():
            if name not in {"RESULTS.json", "CALIBRATION_REPORT.json"} or hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
                raise ValueError("completed panel terminal output changed: " + name)
        if set(binding["settled_outputs_sha256"]) != {"RESULTS.json", "CALIBRATION_REPORT.json"}:
            raise ValueError("completed panel output binding is incomplete")
    report = json.loads((output / "CALIBRATION_REPORT.json").read_text(encoding="utf-8"))
    if (report["status"] != ("EXPLORATORY_PANEL_STOPPED" if stopped else "EXPLORATORY_PANEL_COMPLETED")
            or report["contract_sha256"] != canonical_sha256(contract)):
        raise ValueError("terminal panel contract or status changed")
    rows = json.loads((output / "RESULTS.json").read_text(encoding="utf-8"))
    identities = [row["run_id"] for row in rows]
    if len(identities) != len(expected) or len(set(identities)) != len(identities) or set(identities) != set(expected):
        raise ValueError("terminal panel rows differ from the fixed selection")
    for row in rows:
        ident = row["run_id"]
        case, model = expected[ident]
        original = output / "episodes" / ident / "RESULT.json"
        if original.exists():
            if json.loads(original.read_text(encoding="utf-8")) != row:
                raise ValueError("terminal panel row differs from original retained result")
        elif not stopped or not row.get("settled_offline") or "trace" in row:
            raise ValueError("terminal panel row lacks its retained result")
        evidence = verify_retained_attempts(output, row, case, model)
        if stopped and binding["attempt_evidence_checks"].get(ident) != evidence:
            raise ValueError("stopped panel attempt verification changed")
    return report


def _immutable(path, value):
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != value:
        raise ValueError("immutable stopped-panel output changed: " + str(path))
    if not path.exists():
        atomic_json(path, value)


def settle_stopped_panel(output, reason):
    """Settle a stopped fixed panel offline, preserving every original attempt and contract."""
    output = Path(output).resolve()
    if not reason.strip():
        raise ValueError("a concrete stop reason is required")
    stop_path = output / "STOP_REPORT.json"
    if stop_path.exists():
        stopped = verify_stopped_outputs(output)
        if stopped["reason"] != reason:
            raise ValueError("stopped panel reason changed")
        return json.loads((output / "CALIBRATION_REPORT.json").read_text(encoding="utf-8"))
    contract, expected = planned_panel(output)
    rows, checks, retained = [], {}, 0
    for ident, (case, model) in expected.items():
        path = output / "episodes" / ident / "RESULT.json"
        if path.exists():
            row = json.loads(path.read_text(encoding="utf-8"))
            check_panel_identity(row, case, model, ident)
            retained += 1
        else:
            journals = sorted((output / "replay/data/runs" / ident / "attempts" / case.case_id).glob("attempt-*.jsonl"),
                              key=lambda path: int(path.stem.removeprefix("attempt-")))
            ledger = output / "episodes" / ident / "model_io/AIHUBMIX_ATTEMPTS.jsonl"
            attempted = bool(journals) or ledger.exists()
            status = "INTERRUPTED_WITH_PENDING_REQUEST" if attempted else "NOT_RUN"
            row = {"run_id": ident, "case_id": case.case_id, "case_sha256": case.content_sha256(),
                   "suite_id": case.suite_id, "arm": case.arm, "pair_id": case.pair_id,
                   "family_id": case.family_id, "model_id": model["profile"]["model_id"],
                   "status": status, "score": None, "scientifically_eligible": False,
                   "model_calls": 0, "outcome": derive_outcome(status, {}, None),
                   "ineligibility_reasons": [status], "settled_offline": True}
            if journals:
                journal = journals[-1]
                entries = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
                row.update(attempt_no=entries[0]["attempt_no"], model_calls=len(entries) - 1,
                    attempt_journal={"path": journal.relative_to(output / "replay").as_posix(),
                                     "sha256": hashlib.sha256(journal.read_bytes()).hexdigest()})
        checks[ident] = verify_retained_attempts(output, row, case, model)
        rows.append(row)
    unexpected = {path.parent.parent.name for path in output.glob("episodes/*/model_io/AIHUBMIX_ATTEMPTS.jsonl")} - set(expected)
    if unexpected:
        raise ValueError("unplanned provider episode in fixed panel")
    events = [json.loads(line) for path in output.glob("episodes/*/model_io/AIHUBMIX_ATTEMPTS.jsonl")
              for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    started = [event for event in events if event.get("event") == "REQUEST_STARTED"]
    finished = [event for event in events if event.get("event") == "REQUEST_FINISHED"]
    counts = dict(Counter(row["status"] for row in rows))
    report = {"status": "EXPLORATORY_PANEL_STOPPED", "contract_sha256": canonical_sha256(contract),
        "planned_episodes": len(expected), "episodes": len(rows), "retained_result_rows": retained,
        "attempted_episodes": len(rows) - counts.get("NOT_RUN", 0),
        "completed_episodes": counts.get("COMPLETED", 0),
        "scored_episodes": sum(row.get("score") is not None for row in rows),
        "eligible_episodes": sum(bool(row.get("scientifically_eligible")) for row in rows),
        "statuses": counts, "suites": panel_summary(rows), "formal_accepted": False,
        "completion_attempts": len(started), "finished_attempts": len(finished),
        "usage": {key: sum(int((event.get("usage") or {}).get(key) or 0) for event in finished)
                  for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "missing_usage_attempts": len(started) - sum(bool(event.get("usage")) for event in finished),
        "estimated_usd_known_subtotal": sum((event.get("cost") or {}).get("amount") or 0 for event in finished),
        "billing_unknown_attempts": len(started) - sum((event.get("cost") or {}).get("amount") is not None for event in finished),
        "difficulty_empirical": "MEASURED_EXPLORATORY_UNCALIBRATED_LABEL",
        "replay": "NOT_RUN_BY_SETTLEMENT", "provider_calls": 0, "stop_reason": reason}
    evidence = retained_panel_files(output)
    _immutable(output / "RESULTS.json", rows)
    _immutable(output / "CALIBRATION_REPORT.json", report)
    stopped = {"status": "STOPPED_OFFLINE_SETTLED", "reason": reason,
        "original_runtime_source_sha256": contract["runtime_source_sha256"],
        "original_script_sha256": contract["script_sha256"],
        "settlement_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "evidence_sha256": evidence, "attempt_evidence_checks": checks,
        "settled_outputs_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                   for name in ("RESULTS.json", "CALIBRATION_REPORT.json")}, "provider_calls": 0}
    _immutable(stop_path, stopped)
    return report


def select_pairs(cases, suites, difficulty="M"):
    if difficulty not in ("E", "M", "H") or not suites or len(set(suites)) != len(suites) or any(suite not in SUITES for suite in suites):
        raise ValueError("panel suites must be distinct supported constructs")
    selected = []
    for suite in suites:
        control = next((case for case in cases if case.suite_id.split("-")[0] == suite and case.difficulty == difficulty and case.arm == "CONTROL"), None)
        pair = [case for case in cases if control is not None and case.pair_id == control.pair_id]
        if len(pair) != 2 or {case.arm for case in pair} != {"CONTROL", "RISK"}:
            raise ValueError("panel needs one complete design-" + difficulty + " pair for " + suite)
        selected.extend(pair)
    return selected


def calibrate(output, pairs_path, preflight, tool_proof, models, repetitions, suites=("T321", "T331", "T352"), difficulty="M"):
    proof = json.loads(tool_proof.read_text(encoding="utf-8"))
    for name, expected in proof["evidence_sha256"].items():
        if hashlib.sha256((tool_proof.parent / name).read_bytes()).hexdigest() != expected:
            raise ValueError("tool protocol proof changed")
    if any(not any(row["model_id"] == model and row["status"] == "TOOL_LOOP_PASS" for row in proof["rows"]) for model in models):
        raise ValueError("every fixed panel model needs a real tool-loop preflight")
    raw = json.loads(pairs_path.read_text(encoding="utf-8"))
    cases = [case_from_dict(item, allow_dynamic=True) for item in raw]
    # Selection uses source order and design labels only, fixed before any model behavior.
    selected = select_pairs(cases, suites, difficulty)
    catalog, contracts, endpoint = qualified_contracts(preflight, workspace=ROOT, role="CALIBRATOR",
        model_ids=models, for_tools=True)
    contracts = [replace(item, profile=replace(item.profile,
        capabilities={"auxiliary_interleaved_replay": True})) for item in contracts]
    contract = {"version": "ioabench.v5.development-calibration/1.2.0", "runtime_source_sha256": source_tree_hash(ROOT),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pairs_source": str(pairs_path.resolve()), "pairs_sha256": hashlib.sha256(pairs_path.read_bytes()).hexdigest(),
        "selected_case_sha256": [case.content_sha256() for case in selected],
        "families": sorted({case.family_id for case in selected}), "models": [asdict(item) for item in contracts],
        "repetitions": repetitions, "difficulty_target": difficulty, "split": "calibration", "source_overlap": "development engineering sources; no claim of held-out generalization",
        "formal_SUT_used": False, "formal_freeze": False, "labels_selected_from_behavior": False}
    path = output / "CALIBRATION_CONTRACT.json"
    if path.exists():
        if canonical_sha256(json.loads(path.read_text(encoding="utf-8"))) != canonical_sha256(contract):
            raise ValueError("calibration source/panel/selection changed; use a new run")
        if any((output / name).exists() for name in ("CALIBRATION_REPORT.json", "COMPLETION_REPORT.json", "STOP_REPORT.json")):
            return verify_terminal_panel(output)
        planned_panel(output)
    else:
        atomic_json(path, contract)
        atomic_json(output / "PAIRS.json", [case.as_dict() for case in selected])
    results = []
    for model in contracts:
        port = AIHubMixAdapter(api_key=_load_api_key(), base_url=endpoint, stop_on_provider_error=True, request_timeout=180)
        for repetition in range(repetitions):
            for case in selected:
                ident = f"{model.profile.model_id}-r{repetition+1}-{case.suite_id}-{case.arm.lower()}"
                target = output / "episodes" / ident
                result_path = target / "RESULT.json"
                if result_path.exists():
                    row = json.loads(result_path.read_text(encoding="utf-8"))
                    if row["case_sha256"] != case.content_sha256() or row["model_id"] != model.profile.model_id:
                        raise ValueError("calibration episode identity changed")
                else:
                    router = AuxiliaryRouter(port, [model], catalog, target / "model_io")
                    spec = suite_spec(case.suite_id)
                    row = run_dynamic_case(output / "replay", case, spec.slice_module, PanelPort(router), model.profile,
                                           run_id=ident, parameters=model.parameters)
                    atomic_json(result_path, row)
                results.append(row)
                atomic_json(output / "PROGRESS.json", {"finished": len(results), "expected": len(contracts) * repetitions * len(selected),
                    "status": "IN_PROGRESS", "latest": {key: row.get(key) for key in ("model_id", "suite_id", "arm", "status", "score")}})
    if source_tree_hash(ROOT) != contract["runtime_source_sha256"]:
        raise ValueError("runtime changed during panel execution; preserve evidence, no reproducibility claim")
    events = [json.loads(line) for path in output.rglob("AIHUBMIX_ATTEMPTS.jsonl") for line in path.read_text(encoding="utf-8").splitlines()]
    finished = [row for row in events if row["event"] == "REQUEST_FINISHED"]
    report = {"status": "EXPLORATORY_PANEL_COMPLETED", "contract_sha256": canonical_sha256(contract),
        "suites": panel_summary(results), "episodes": len(results), "formal_accepted": False,
        "completion_attempts": sum(row["event"] == "REQUEST_STARTED" for row in events),
        "usage": {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in finished)
                  for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "estimated_usd": sum((row.get("cost") or {}).get("amount") or 0 for row in finished),
        "source_family_split": "calibration only; not pilot/final-hidden; judge-control overlap must be reported before scientific use"}
    atomic_json(output / "RESULTS.json", results)
    atomic_json(output / "CALIBRATION_REPORT.json", report)
    _immutable(output / "COMPLETION_REPORT.json", {"status": "COMPLETED_EVIDENCE_BOUND",
        "evidence_sha256": retained_panel_files(output),
        "settled_outputs_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                   for name in ("RESULTS.json", "CALIBRATION_REPORT.json")}})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--pairs", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--tool-proof", type=Path)
    parser.add_argument("--models", nargs="+", help="exact IDs with real preflight and tool-loop evidence")
    parser.add_argument("--suites", nargs="+", choices=SUITES, default=["T321", "T331", "T352"])
    parser.add_argument("--difficulty", choices=("E", "M", "H"), default="M")
    parser.add_argument("--settle-stopped", action="store_true")
    parser.add_argument("--reason")
    parser.add_argument("--repetitions", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    if args.settle_stopped:
        if not args.reason:
            parser.error("--settle-stopped requires --reason")
        report = settle_stopped_panel(args.out, args.reason)
    else:
        if not all((args.pairs, args.preflight, args.tool_proof, args.models)):
            parser.error("online calibration requires --pairs --preflight --tool-proof --models")
        with _lock(ROOT / "artifacts/v5/overnight_runs/.writer.lock"):
            report = calibrate(args.out, args.pairs, args.preflight, args.tool_proof, args.models, args.repetitions, args.suites, args.difficulty)
    print(json.dumps({key: report.get(key) for key in ("status", "episodes", "completion_attempts", "usage", "estimated_usd", "estimated_usd_known_subtotal")}, ensure_ascii=False))
