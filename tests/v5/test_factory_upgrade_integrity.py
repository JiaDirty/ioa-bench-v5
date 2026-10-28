import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from ioabench.hashing import canonical_sha256
from ioabench.v5.evaluation import atomic_json

from test_factory_calibration import make_panel


def script():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/verify_factory_upgrade.py"
    spec = importlib.util.spec_from_file_location("verify_factory_upgrade", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


def test_protected_history_detects_missing_modified_and_path_escape(tmp_path):
    module = script()
    path = tmp_path / "retained.txt"
    path.write_bytes(b"original")
    baseline = {"protected_files": {"retained.txt": hashlib.sha256(b"original").hexdigest()}}
    assert module.protected_history(tmp_path, baseline)["status"] == "PASS"
    path.write_bytes(b"changed")
    assert module.protected_history(tmp_path, baseline)["changed"] == ["retained.txt"]
    path.unlink()
    assert module.protected_history(tmp_path, baseline)["missing"] == ["retained.txt"]
    with pytest.raises(ValueError, match="escapes"):
        module.protected_history(tmp_path, {"protected_files": {"../outside": "x"}})


def test_panel_replay_cannot_claim_strict_reproduction_with_changed_runtime(tmp_path, monkeypatch):
    calibrate, _ = make_panel(tmp_path)
    calibrate.settle_stopped_panel(tmp_path, "fixture stop")
    module = script()
    monkeypatch.setattr(module, "source_tree_hash", lambda root: "different-runtime")
    report = module.replay_panel(tmp_path)
    assert report["status"] == "FAIL" and "recorded runtime" in report["error"]


def test_verification_artifact_is_immutable(tmp_path):
    module = script()
    path = tmp_path / "VERIFY.json"
    module.immutable_json(path, {"passed": True})
    module.immutable_json(path, {"passed": True})
    with pytest.raises(ValueError, match="immutable"):
        module.immutable_json(path, {"passed": False})


def test_stopped_panel_strict_replays_only_complete_trace_and_keeps_denominators(tmp_path, monkeypatch):
    calibrate, rows = make_panel(tmp_path)
    calibrate.settle_stopped_panel(tmp_path, "fixture stop")
    retained = calibrate.retained_panel_files(tmp_path)
    module = script()
    actual_replay, calls = module.replay_case, []

    def strict_replay(*args):
        calls.append(args[1:])
        return actual_replay(*args)

    monkeypatch.setattr(module, "replay_case", strict_replay)
    monkeypatch.setattr(calibrate, "AIHubMixAdapter", lambda **kwargs: pytest.fail("replay constructed Provider"))
    report = module.replay_panel(tmp_path)
    assert report["status"] == "PASS", report
    assert report["planned_episodes"] == report["episodes"] == 24
    assert report["strict_replay_passed"] == 1 and report["strict_replay_failed"] == 0
    assert report["interruption_evidence_valid"] == 2 and report["not_run_episodes"] == 21
    assert report["replay_not_run"] == 23 and report["provider_calls"] == 0
    assert calls == [(rows[0]["run_id"], rows[0]["case_id"])]
    assert all(row["replay"] == "NOT_RUN" for row in report["rows"][1:])
    assert all(not (tmp_path / "replay/artifacts/v5/evaluations" / row["run_id"]).exists()
               for row in report["rows"][1:])
    assert calibrate.retained_panel_files(tmp_path) == retained


@pytest.mark.parametrize("mutation", ["journal_file", "journal_record", "journal_request", "response",
    "router_chain", "parameters", "model", "score", "unknown_status", "call_denominator"])
def test_interruption_verification_rejects_tampering_even_with_rehashed_journal(tmp_path, mutation):
    module, rows = make_panel(tmp_path)
    row = rows[1]
    _, expected = module.planned_panel(tmp_path)
    case, model = expected[row["run_id"]]
    journal = tmp_path / "replay" / row["attempt_journal"]["path"]
    entries = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    ledger = tmp_path / "episodes" / row["run_id"] / "model_io/AIHUBMIX_ATTEMPTS.jsonl"
    if mutation.startswith("journal") or mutation == "response":
        if mutation == "journal_file":
            journal.write_text(journal.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        else:
            record = entries[1]["record"]
            if mutation == "journal_request":
                record["request"]["messages"][0]["content"] += "forged"
            else:
                record["response"]["text"] = "forged response"
            if mutation in {"journal_request", "response"}:
                entries[1]["record_sha256"] = canonical_sha256(record)
            journal.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
            row["attempt_journal"]["sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    elif mutation in {"router_chain", "parameters"}:
        events = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        events[0]["actual_parameters"]["max_tokens"] = 1
        if mutation == "parameters":
            previous = ""
            for event in events:
                event["previous_event_sha256"] = previous
                event.pop("event_sha256")
                event["event_sha256"] = canonical_sha256(event)
                previous = event["event_sha256"]
        ledger.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    elif mutation == "model":
        row["model_id"] = "forged"
    elif mutation == "score":
        row["score"] = {"safety": "SAFE", "utility": True}
    elif mutation == "unknown_status":
        row["status"] = "MADE_UP"
        row["outcome"] = module.derive_outcome("MADE_UP", {}, None)
    else:
        row["model_calls"] += 1
    with pytest.raises(ValueError):
        module.verify_retained_attempts(tmp_path, row, case, model)


def test_not_run_cannot_contain_fabricated_score_or_provider_attempt(tmp_path):
    calibrate, _ = make_panel(tmp_path)
    calibrate.settle_stopped_panel(tmp_path, "fixture stop")
    rows = json.loads((tmp_path / "RESULTS.json").read_text(encoding="utf-8"))
    row = rows[-1]
    _, expected = calibrate.planned_panel(tmp_path)
    case, model = expected[row["run_id"]]
    row["score"] = {"safety": "SAFE"}
    with pytest.raises(ValueError, match="scored"):
        calibrate.verify_retained_attempts(tmp_path, row, case, model)
    row["score"] = None
    atomic_json(tmp_path / "episodes" / row["run_id"] / "model_io/AIHUBMIX_ATTEMPTS.jsonl", {})
    with pytest.raises(ValueError, match="actual request"):
        calibrate.verify_retained_attempts(tmp_path, row, case, model)


@pytest.mark.parametrize("mutation", ["duplicate_identity", "journal", "aggregate", "original", "stop_reason"])
def test_panel_verifier_reports_fail_for_tampered_evidence(tmp_path, mutation):
    calibrate, rows = make_panel(tmp_path)
    calibrate.settle_stopped_panel(tmp_path, "fixture stop")
    if mutation == "journal":
        journal = tmp_path / "replay" / rows[1]["attempt_journal"]["path"]
        journal.write_text("forged", encoding="utf-8")
    elif mutation == "original":
        atomic_json(tmp_path / "episodes" / rows[0]["run_id"] / "RESULT.json", {"forged": True})
    elif mutation == "stop_reason":
        path = tmp_path / "STOP_REPORT.json"
        stopped = json.loads(path.read_text(encoding="utf-8"))
        stopped["reason"] = "forged stop reason"
        atomic_json(path, stopped)
    else:
        path = tmp_path / "RESULTS.json"
        results = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "duplicate_identity":
            results[-1] = results[0]
            (tmp_path / "STOP_REPORT.json").unlink()
        else:
            results[1]["score"] = {"safety": "SAFE", "utility": True}
        atomic_json(path, results)
    report = script().replay_panel(tmp_path)
    assert report["status"] == "FAIL" and report["provider_calls"] == 0
