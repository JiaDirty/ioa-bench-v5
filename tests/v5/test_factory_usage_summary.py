from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("factory_usage_summary", ROOT / "scripts/v5/summarize_factory_usage.py")
COMMAND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMMAND)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def ledger(directory, events):
    directory.mkdir(parents=True, exist_ok=True)
    previous, lines = "", []
    for event in events:
        row = {"previous_event_sha256": previous, **event}
        row["event_sha256"] = canonical_sha256(row)
        previous = row["event_sha256"]
        lines.append(json.dumps(row))
    path = directory / "AIHUBMIX_ATTEMPTS.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def router_fixture(directory):
    events = []
    for index, status in enumerate(("SUCCEEDED", "FAILED", "REQUEST_UNRESOLVED", None)):
        row = {"attempt_id": f"attempt-{index}", "request_id": f"task-{index}",
               "role": "GENERATOR" if index < 2 else "CALIBRATOR",
               "requested_model_id": "exact-a" if index < 2 else "exact-b",
               "request_sha256": str(index), "status": "REQUEST_STARTED"}
        events.append({"event": "REQUEST_STARTED", **row})
        if status:
            finish = {**row, "status": status}
            if status == "SUCCEEDED":
                finish.update(served_model_id="exact-a", response={"model_id": "served-response-a"},
                              usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                              cost={"status": "ESTIMATED", "currency": "USD", "amount": 0.1})
            events.append({"event": "REQUEST_FINISHED", **finish})
    path = ledger(directory, events)
    put(directory / "wrappers/GENERATOR_RESPONSE.json", {"usage": {"total_tokens": 99999999}})
    return path


def control_fixture(directory, *, completed=True, bind=True):
    put(directory / "CONTROL_CONTRACT.json", {"auditor": "auditor-exact"})
    for ordinal in range(2 if completed else 1):
        target = directory / str(ordinal)
        request = {"role": "INDEPENDENT_AUDITOR", "requested_model_id": "auditor-exact"}
        digest = canonical_sha256(request)
        put(target / "AUDITOR_REQUEST.json", request)
        events = [{"event": "REQUEST_STARTED", "role": "AUDITOR", "model_id": "auditor-exact", "request_sha256": digest}]
        if completed:
            put(target / "AUDITOR_RESPONSE.json", {"request_sha256": digest, "model_id": "response-auditor",
                "provider_metadata": {"transport_metadata": {"x-aihubmix-model": "auditor-exact"}},
                "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9}})
            events.extend([{"event": "RESPONSE_SAVED", "role": "AUDITOR"},
                           {"event": "RESPONSE_REPLAYED", "role": "AUDITOR"}])
        else:
            events.append({"event": "REQUEST_FAILED", "role": "AUDITOR"})
        path = target / "EXECUTION_LOG.jsonl"
        path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    if completed:
        report = {"auditor": "auditor-exact", "monetary_cost": {"status": "ESTIMATED", "currency": "USD", "amount": 0.25}}
        if bind:
            report["evidence_sha256"] = {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                         for path in directory.rglob("*") if path.is_file()}
        put(directory / "CONTROL_RESULT.json", report)


def test_overlapping_roots_and_response_wrappers_never_double_count_attempts(tmp_path):
    router = tmp_path / "routers/one"
    router_fixture(router)
    report = COMMAND.build_summary(router_dirs=[tmp_path / "routers", router, router])
    totals = report["totals"]
    assert len(report["router_ledgers"]) == 1
    assert totals["attempts_started"] == 4 and totals["attempts_finished"] == 3
    assert (totals["attempts_succeeded"], totals["attempts_failed"], totals["attempts_unresolved"]) == (1, 1, 2)
    assert totals["known_tokens"]["total_tokens"] == 120
    assert totals["missing_token_counts"]["total_tokens"] == 3
    assert totals["monetary_cost"]["amount"] == 0.1
    assert totals["monetary_cost"]["unknown_billing_attempts"] == 3
    assert totals["exact_served_model_ids"] == ["exact-a"]
    assert report["attempts"][0]["response_model_id"] == "served-response-a"
    assert len(report["by_request_directory"]) == 4


def test_gold_cost_is_counted_once_without_inventing_per_request_prices(tmp_path):
    gold, failed = tmp_path / "gold/complete", tmp_path / "gold/failed"
    control_fixture(gold)
    control_fixture(failed, completed=False)
    report = COMMAND.build_summary(control_dirs=[tmp_path / "gold", gold])
    totals = report["totals"]
    assert totals["attempts_started"] == 3 and totals["attempts_finished"] == 3
    assert totals["attempts_succeeded"] == 2 and totals["attempts_failed"] == 1
    assert totals["known_tokens"] == {"prompt_tokens": 8, "completion_tokens": 10, "total_tokens": 18}
    assert totals["missing_token_counts"]["total_tokens"] == 1
    assert totals["monetary_cost"]["amount"] == 0.25
    assert totals["monetary_cost"]["unknown_billing_attempts"] == 1
    assert len(report["aggregate_cost_pools"]) == 1
    assert all(row["cost"]["amount"] is None for row in report["attempts"])
    assert all(row["monetary_cost"]["amount"] == 0 for row in report["by_request_directory"])
    assert report["by_model"][0]["monetary_cost"]["amount"] == 0.25


def test_router_hash_chain_tampering_stops_summary(tmp_path):
    path = router_fixture(tmp_path)
    content = path.read_text(encoding="utf-8").replace('"prompt_tokens": 100', '"prompt_tokens": 101')
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        COMMAND.build_summary(router_dirs=[tmp_path])


def test_bound_gold_response_tampering_stops_summary(tmp_path):
    control_fixture(tmp_path)
    path = tmp_path / "0/AUDITOR_RESPONSE.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["usage"]["total_tokens"] = 100000
    put(path, value)
    with pytest.raises(ValueError, match="hash changed"):
        COMMAND.build_summary(control_dirs=[tmp_path])


def test_replayed_response_has_no_new_paid_request_and_output_is_immutable(tmp_path):
    control_fixture(tmp_path / "gold")
    output = tmp_path / "summary.json"
    args = ["--control-dir", str(tmp_path / "gold"), "--output", str(output)]
    assert COMMAND.main(args) == 0
    original = output.read_bytes()
    assert json.loads(original)["totals"]["attempts_started"] == 2
    with pytest.raises(FileExistsError):
        COMMAND.main(args)
    assert output.read_bytes() == original


def test_partial_usage_and_failed_returned_response_keep_actual_tokens(tmp_path):
    record = {"attempt_id": "a", "request_id": "r", "role": "GENERATOR",
              "requested_model_id": "exact-a", "request_sha256": "h"}
    ledger(tmp_path, [{"event": "REQUEST_STARTED", **record, "status": "REQUEST_STARTED"},
        {"event": "REQUEST_FINISHED", **record, "status": "FAILED", "usage": {"prompt_tokens": 7},
         "served_model_id": "wrong-exact-id", "category": "MODEL_IDENTITY"}])
    totals = COMMAND.build_summary(router_dirs=[tmp_path])["totals"]
    assert totals["attempts_failed"] == 1 and totals["known_tokens"]["prompt_tokens"] == 7
    assert totals["missing_token_counts"]["completion_tokens"] == 1
    assert totals["monetary_cost"]["unknown_billing_attempts"] == 1
    assert totals["exact_served_model_ids"] == ["wrong-exact-id"]


def test_control_missing_usage_keeps_billing_unknown_even_with_run_cost(tmp_path):
    control_fixture(tmp_path, bind=False)
    path = tmp_path / "0/AUDITOR_RESPONSE.json"
    response = json.loads(path.read_text(encoding="utf-8"))
    response.pop("usage")
    put(path, response)
    report = COMMAND.build_summary(control_dirs=[tmp_path])
    assert report["totals"]["monetary_cost"]["amount"] == 0.25
    assert report["totals"]["monetary_cost"]["unknown_billing_attempts"] == 1
    assert report["totals"]["missing_token_counts"]["total_tokens"] == 1
