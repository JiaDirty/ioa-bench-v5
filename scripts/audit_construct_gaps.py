"""Offline construct audit; historical runs and datasets are read-only."""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import fields
import hashlib
from importlib import import_module
import json
from pathlib import Path, PurePosixPath
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ioabench.hashing import canonical_sha256
from ioabench.models import MockModel, ModelResponse
from ioabench.runtime.offline_run import SUITES, _independent_evidence, execute_mock_case
from ioabench.runtime.scheduler import WorkScheduler
from ioabench.telemetry import NormalizedEvent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def event_objects(replay):
    allowed = {field.name for field in fields(NormalizedEvent)}
    return [NormalizedEvent(**{**{key: value for key, value in event.items() if key in allowed},
                              "run_id": replay["run_id"], "case_id": replay["case_id"]})
            for event in replay["timeline"]]


def score(suite, events):
    module = import_module(f"ioabench.suites.{suite.lower()}.scoring")
    return getattr(module, f"{suite}Scorer")().score(events).as_dict()


def digest_tree(paths):
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for parent in paths for path in sorted(parent.rglob("*")) if path.is_file()}


def self_check():
    from ioabench.replay.bundle import _event_dict
    event = NormalizedEvent.create(run_id="test", case_id="test", event_type="risk.exposed", stage="EXPOSURE")
    rebuilt = event_objects({"run_id": "test", "case_id": "test", "timeline": [_event_dict(event)]})
    assert rebuilt[0].event_id == event.event_id
    assert score("T342", rebuilt)["outcome_class"] == "TASK_SAFE_BUT_FAILED"
    unsafe = NormalizedEvent.create(run_id="test", case_id="test", event_type="rumor.accept", stage="ACTION", outcome="UNSAFE")
    assert score("T342", [event, unsafe])["outcome_class"] == "UNSAFE_ACTION"


def audit(run_id):
    run_root = ROOT / "data/runs" / run_id
    manifest = read_json(run_root / "manifest" / f"{run_id}.json")
    results = read_json(run_root / "results.json")
    protected = [ROOT / "data/runs", ROOT / "data/datasets"]
    before = digest_tree(protected)
    evidence = {"run_id": run_id, "scope": "construct audit, not scientific acceptance", "suites": {},
                "manifest_sha256": manifest.get("manifest_sha256"), "no_network": True}
    totals = Counter()
    response_ids = set()
    sources = list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
    evidence["source_sha256"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(sources)}
    with tempfile.TemporaryDirectory(prefix="ioa-construct-probes-") as temporary:
        for suite in SUITES:
            version = manifest["benchmark"]["dataset_versions"][suite]
            dataset_root = ROOT / "data/datasets" / suite / version
            dataset_manifest = read_json(dataset_root / "manifest.json")
            cases = [json.loads(line) for line in (dataset_root / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
            by_id = {case["candidate_id"]: case for case in cases}
            counts, event_counts, sequences, outcomes, joint, snapshots = (Counter() for _ in range(6))
            samples, replay_cache = [], []
            for work_id, result in sorted(results.items()):
                if result["suite"] != suite:
                    continue
                replay_path = run_root / result["replay"].replace("\\", "/")
                replay = read_json(replay_path)
                case = by_id[result["case_id"]]
                events, records = event_objects(replay), replay["model_records"]
                counts["cases"] += 1
                counts["hash_match"] += canonical_sha256({key: value for key, value in replay.items() if key != "content_sha256"}) == replay["content_sha256"] == result["replay_sha256"]
                counts["payload_equal"] += replay["scenario"]["sut_payload"] == case["sut_payload"]
                counts["rescore_equal"] += score(suite, events) == result["score"]
                rescored = score(suite, events)
                counts["rescore_values_equal"] += {key: value for key, value in rescored.items() if key not in {"safety_evidence", "utility_evidence"}} == {key: value for key, value in result["score"].items() if key not in {"safety_evidence", "utility_evidence"}}
                counts["rescore_evidence_sets_equal"] += all(set(rescored[key]) == set(result["score"][key]) for key in ("safety_evidence", "utility_evidence"))
                counts["two_tested_one_scripted"] += Counter(agent["model_role"] for agent in replay["agents"]) == {"TESTED": 2, "SCRIPTED": 1}
                counts["windows_relative_path"] += "\\" in result["replay"]
                counts["posix_path_one_component"] += len(PurePosixPath(result["replay"]).parts) == 1
                event_counts.update(event.event_type for event in events)
                sequence = [call.get("function", {}).get("name") for record in records for call in record["response"].get("tool_calls", [])]
                sequences[" -> ".join(sequence)] += 1
                outcomes[result["score"]["outcome_class"]] += 1
                snapshots[json.dumps(sorted(replay["world_snapshot"]))] += 1
                counts["task_success"] += bool(replay["final_utility"]["task_success"])
                counts["unsafe_tool_but_early_safe"] += result["score"]["outcome_class"] == "EARLY_SAFE" and any(event.event_type == "tool.call.result" and event.outcome == "UNSAFE" for event in events)
                peer_records = [record for record in records if record["agent_id"] == "agent-2"]
                peer = peer_records[0]
                counts["peer_empty"] += not bool((peer["response"].get("text") or "").strip())
                counts["peer_length_finish"] += peer["response"].get("finish_reason") == "length"
                counts["peer_has_tools"] += bool(peer["request"]["tools"])
                counts["peer_calls"] += len(peer_records)
                counts["lead_calls"] += len(records) - len(peer_records)
                for record in records:
                    response_ids.add(record.get("provider_response_id"))
                    users = [message for message in record["request"]["messages"] if message.get("role") == "user"]
                    counts["visible_record_mismatch"] += any(json.loads(message["content"]).get("visible_record") != case["sut_payload"] for message in users)
                lead = [record for record in records if record["agent_id"] == "agent-1"]
                counts["first_lead_request_has_future_tool_messages"] += any(message.get("role") == "tool" for message in lead[0]["request"]["messages"])
                counts["all_lead_requests_identical"] += len(lead) > 1 and all(record["request"]["messages"] == lead[0]["request"]["messages"] for record in lead[1:])
                counts["empty_peer_delivered"] += not bool(json.loads(lead[0]["request"]["messages"][1]["content"]).get("peer_message", "").strip())
                counts["scenario_budget_differs"] += replay["scenario"]["budgets"]["max_tool_calls"] != manifest["runtime"]["action_budget"]["max_tool_calls"]
                joint[f"{case['provenance']['condition']}|{result['score']['outcome_class']}|utility={replay['final_utility']['task_success']}"] += 1
                replay_cache.append((replay_path, replay, result, case))
            selected = {}
            for condition in ("RISK", "CONTROL"):
                for difficulty in ("easy", "medium", "hard"):
                    match = next((item for item in replay_cache if item[3]["provenance"]["condition"] == condition and item[3]["difficulty"].lower() == difficulty), None)
                    if match:
                        selected[str(match[0])] = match
            for predicate in (lambda item: item[2]["score"]["outcome_class"] in {"UNSAFE_ACTION", "FULL_FAILURE"},
                              lambda item: any(record["agent_id"] == "agent-2" and bool(record["response"].get("text")) for record in item[1]["model_records"]),
                              lambda item: item[2]["score"]["outcome_class"] == "EARLY_SAFE" and any(event["event_type"] == "tool.call.result" and event.get("outcome") == "UNSAFE" for event in item[1]["timeline"])):
                match = next((item for item in replay_cache if predicate(item)), None)
                if match:
                    selected[str(match[0])] = match
            for replay_path, replay, result, case in selected.values():
                events = event_objects(replay)
                without_generic = [event for event in events if not event.event_type.startswith(("tool.", "model.")) and event.event_type not in {"task.completed", "task.failed", "task.refused"}]
                without_renamed = [event for event in events if event.attributes.get("source_action") != "complete_task"]
                samples.append({"path": replay_path.relative_to(ROOT).as_posix(), "case_id": case["candidate_id"], "difficulty": case["difficulty"],
                    "condition": case["provenance"]["condition"], "score": result["score"], "final_utility": replay["final_utility"],
                    "dataset_fields": sorted(case["sut_payload"]), "oracle": case["oracle_payload"],
                    "source_evidence": replay["world_snapshot"].get("evidence_record"), "world_snapshot_keys": sorted(replay["world_snapshot"]),
                    "models": [{"agent": record["agent_id"], "text": record["response"].get("text"), "finish_reason": record["response"].get("finish_reason"),
                                "tools": [call.get("function", {}).get("name") for call in record["response"].get("tool_calls", [])], "usage": record.get("usage")} for record in replay["model_records"]],
                    "scoring_events": [{"id": event.event_id, "type": event.event_type, "outcome": event.outcome, "attributes": dict(event.attributes)} for event in events if event.event_id in result["score"]["safety_evidence"]],
                    "delete_generic_execution_events_score": score(suite, without_generic), "delete_mapped_unsafe_events_score": score(suite, without_renamed)})
            risk = next(case for case in cases if case["provenance"]["condition"] == "RISK")
            unit = WorkScheduler().expand("mock", suite, version, [risk])[0]
            baseline = {}
            for model_id in ("mock", "naive"):
                result = asyncio.run(execute_mock_case(ROOT, unit, risk, Path(temporary) / suite / model_id, model_id))
                baseline[model_id] = result["score"]
            original_evidence = _independent_evidence(suite, risk, risk["sut_payload"])
            from ioabench.sandbox import SandboxCore
            original_apply = SandboxCore._apply
            def suppress_write(sandbox, operation, arguments):
                if operation == "set":
                    return {"key": arguments["key"], "value": sandbox._state.get(arguments["key"])}
                return original_apply(sandbox, operation, arguments)
            noop_root = Path(temporary) / suite / "no_state_change"
            with patch.object(SandboxCore, "_apply", suppress_write):
                noop_result = asyncio.run(execute_mock_case(ROOT, unit, risk, noop_root, "naive"))
            noop_replay = read_json(noop_root / noop_result["replay"])
            noop_probe = {"score": noop_result["score"], "actual_task_status": noop_replay["world_snapshot"]["task_status"], "reported_utility": noop_replay["final_utility"]["task_success"]}
            perturbations = {}
            for key, value in risk["oracle_payload"].items():
                altered = deepcopy(risk)
                if isinstance(value, bool):
                    altered["oracle_payload"][key] = not value
                elif isinstance(value, str) and key != "condition":
                    altered["oracle_payload"][key] = "AUDIT_SENTINEL"
                else:
                    continue
                changed = _independent_evidence(suite, altered, risk["sut_payload"])
                if changed != original_evidence:
                    perturbations[key] = {"before": original_evidence, "after": changed}
            responses = [ModelResponse("Audit peer assessment"),
                         ModelResponse(None, tool_calls=({"id": "q", "type": "function", "function": {"name": "query_source_record", "arguments": "{}"}},)),
                         ModelResponse(None, tool_calls=({"id": "c", "type": "function", "function": {"name": "complete_task", "arguments": "{}"}},))]
            with patch("ioabench.runtime.offline_run.MockModel", return_value=MockModel(responses)):
                result = asyncio.run(execute_mock_case(ROOT, unit, risk, Path(temporary) / suite / "query_then_complete", "mock"))
            evidence["suites"][suite] = {"version": version, "dataset_hash_valid": canonical_sha256({"manifest": {**dataset_manifest, "content_sha256": None}, "cases": cases}) == manifest["benchmark"]["dataset_hashes"][suite],
                "counts": dict(counts), "outcomes": dict(outcomes), "condition_outcome_utility": dict(joint), "tool_sequences": dict(sequences), "event_counts": dict(event_counts),
                "world_snapshot_key_sets": dict(snapshots), "dataset_top_level_fields": sorted({key for case in cases for key in case["sut_payload"]}),
                "difficulty_counts": dict(Counter(case["difficulty"] for case in cases)), "condition_counts": dict(Counter(case["provenance"]["condition"] for case in cases)),
                "baseline": baseline, "suppressed_state_change": noop_probe, "query_then_complete_risk_score": result["score"], "oracle_only_mutation_changes_evidence": perturbations, "samples": samples}
            totals.update(counts)
            print(suite, dict(counts), dict(outcomes), flush=True)
    after = digest_tree(protected)
    assert before == after, "Historical run or frozen dataset changed"
    evidence["protected_files_unchanged"] = len(before)
    evidence["protected_tree_digest"] = canonical_sha256(before)
    evidence["totals"] = dict(totals)
    evidence["unique_provider_response_ids"] = len(response_ids - {None})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="deepseek-v4.1-flash-v1-pack-v2-r5")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if any(parent in output.parents for parent in (ROOT / "data/runs", ROOT / "data/datasets")):
        raise ValueError("Audit output must not be inside runs or datasets")
    original_connect = socket.socket.connect
    def local_connect(connection, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(connection, address)
        raise RuntimeError("External network disabled by construct audit")
    def deny_provider(*args, **kwargs):
        raise RuntimeError("Provider disabled by construct audit")
    with patch.object(socket.socket, "connect", local_connect), patch("ioabench.runtime.offline_run.AIHubMixAdapter", side_effect=deny_provider):
        self_check()
        evidence = audit(args.run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("Audit evidence:", output)


if __name__ == "__main__":
    main()
