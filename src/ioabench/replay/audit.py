"""Evaluator-side integrity checks for persisted replay bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ioabench.hashing import canonical_sha256


def audit_run(root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(root)
    run_root = root / "data" / "runs" / run_id
    records = json.loads((run_root / "results.json").read_text(encoding="utf-8"))
    manifest_files = sorted((run_root / "manifest").glob("*.json"))
    if len(manifest_files) != 1:
        return {"schema_version": "1.0", "run_id": run_id, "status": "FAIL", "audited_valid_units": 0, "excluded_units": 0, "failures": [{"work_id": "manifest", "reason": "run must contain exactly one frozen manifest"}]}
    manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    dataset_cache: dict[tuple[str, str], dict[str, Any]] = {}
    checked = 0
    failures: list[dict[str, str]] = []
    excluded = 0
    for work_id, record in records.items():
        if record.get("eligibility") != "VALID":
            excluded += 1
            continue
        checked += 1
        replay_path = (run_root / str(record.get("replay", "")).replace("\\", "/")).resolve()
        if run_root.resolve() not in replay_path.parents or not replay_path.is_file():
            failures.append({"work_id": work_id, "reason": "replay missing"})
            continue
        try:
            replay = json.loads(replay_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append({"work_id": work_id, "reason": "replay is not valid JSON"})
            continue
        content_hash = replay.get("content_sha256")
        body = dict(replay)
        body.pop("content_sha256", None)
        if canonical_sha256(body) != content_hash or content_hash != record.get("replay_sha256"):
            failures.append({"work_id": work_id, "reason": "canonical replay hash mismatch"})
            continue
        timeline = replay.get("timeline", [])
        model_records = replay.get("model_records", [])
        if not timeline or not model_records:
            failures.append({"work_id": work_id, "reason": "replay lacks observable timeline or model records"})
            continue
        if replay.get("scenario", {}).get("construct_contract_version"):
            for index, model_record in enumerate(model_records):
                request = model_record.get("request", {})
                if model_record.get("request_sha256") != canonical_sha256(request):
                    failures.append({"work_id": work_id, "reason": f"model request snapshot mismatch at {index}"})
                    break
                input_event = next((item for item in timeline if item.get("event_type") == "model.input" and item.get("attributes", {}).get("model_record_index") == index), None)
                if input_event is None or input_event.get("payload_sha256") != canonical_sha256(request):
                    failures.append({"work_id": work_id, "reason": f"model input chronology mismatch at {index}"})
                    break
        event_ids = [item.get("event_id") for item in timeline if item.get("event_id")]
        derived = {"event_ids": event_ids, "model_record_ids": [item.get("record_id") for item in model_records if item.get("record_id")], "utility": replay.get("final_utility", {})}
        if not derived["event_ids"] or not derived["model_record_ids"]:
            failures.append({"work_id": work_id, "reason": "scorer inputs cannot be reconstructed"})
            continue
        if _contains_oracle_key(_public_view(replay.get("scenario", {}))) or _contains_oracle_key(_public_view(replay.get("model_records", []))):
            failures.append({"work_id": work_id, "reason": "Oracle-only key appears in model-visible replay inputs"})
            continue
        suite = str(record.get("suite", replay.get("scenario", {}).get("test_id", "")))
        version = str(manifest.get("benchmark", {}).get("dataset_versions", {}).get(suite, ""))
        case_key = (suite, version)
        if case_key not in dataset_cache:
            dataset_dir = root / "data" / "datasets" / suite / version
            dataset_manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
            expected_hash = manifest.get("benchmark", {}).get("dataset_hashes", {}).get(suite)
            if dataset_manifest.get("content_sha256") != expected_hash:
                failures.append({"work_id": work_id, "reason": "frozen manifest dataset hash does not match dataset"})
                continue
            dataset_cache[case_key] = {
                item["candidate_id"]: item
                for item in (json.loads(line) for line in (dataset_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line)
            }
        frozen_case = dataset_cache[case_key].get(str(record.get("case_id")))
        if frozen_case is None:
            failures.append({"work_id": work_id, "reason": "case is absent from manifest-pinned dataset"})
            continue
        scenario = replay.get("scenario", {})
        if scenario.get("sut_payload") != frozen_case.get("sut_payload"):
            failures.append({"work_id": work_id, "reason": "replay SUT-visible payload differs from frozen dataset"})
            continue
        if scenario.get("sut_payload_sha256") != canonical_sha256(frozen_case.get("sut_payload", {})):
            failures.append({"work_id": work_id, "reason": "replay SUT-visible payload hash mismatch"})
            continue
        visible_records = []
        for model_record in model_records:
            messages = model_record.get("request", {}).get("messages", [])
            for message in messages:
                if message.get("role") != "user" or not isinstance(message.get("content"), str):
                    continue
                try:
                    content = json.loads(message["content"])
                except json.JSONDecodeError:
                    continue
                if isinstance(content, dict) and "visible_record" in content:
                    visible_records.append(content["visible_record"])
        if not visible_records or any(value != frozen_case.get("sut_payload") for value in visible_records):
            failures.append({"work_id": work_id, "reason": "model-visible record differs from frozen dataset"})
    return {"schema_version": "1.0", "run_id": run_id, "status": "PASS" if not failures else "FAIL", "audited_valid_units": checked, "excluded_units": excluded, "failures": failures}


def _contains_oracle_key(value: Any) -> bool:
    hidden = {"oracle", "oracle_db", "oracle_path", "ground_truth", "hidden_truth", "truth_label", "attack_label", "scoring_rules", "oracle_ref", "oracle_refs"}
    if isinstance(value, dict):
        return any(str(key).casefold() in hidden or _contains_oracle_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_oracle_key(item) for item in value)
    return False


def _public_view(value: Any) -> Any:
    hidden = {"oracle", "oracle_db", "oracle_path", "ground_truth", "hidden_truth", "truth_label", "attack_label", "scoring_rules", "oracle_ref", "oracle_refs"}
    if isinstance(value, dict):
        return {key: _public_view(item) for key, item in value.items() if str(key).casefold() not in hidden}
    if isinstance(value, list):
        return [_public_view(item) for item in value]
    return value
