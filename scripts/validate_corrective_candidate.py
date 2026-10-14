"""Offline behavioral checks for an isolated, unapproved corrective candidate."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    candidate = args.candidate.resolve()
    if candidate == root or not (candidate / "src/ioabench").is_dir():
        raise ValueError("An isolated candidate source directory is required")
    if args.output.exists():
        raise FileExistsError(args.output)
    sys.path.insert(0, str(candidate / "src"))
    from ioabench.hashing import canonical_sha256
    from ioabench.models import ModelProfile
    from ioabench.runtime.batch import BatchRunner
    from ioabench.runtime.construct_dispatch import execute_construct_case
    from ioabench.runtime.discovery_selection import DiscoverySelectionBaseline
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.runtime.scheduler import WorkUnit
    from ioabench.suites.t353.construct_scoring import score_t353

    checks = {}
    failures = []
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            failures.append(name)

    source_before = source_tree_hash(root)
    statuses = ("COMPLETED", "INVALID_MODEL_OUTPUT", "UNSUPPORTED", "INVALID_RUN", "FAILED", "CANCELLED", "RETRYABLE_INFRA_FAILURE")
    with tempfile.TemporaryDirectory(prefix="ioa-candidate-check-") as temporary:
        state_path = Path(temporary) / "checkpoint.json"
        before = {s: {"status": s, "sentinel": s} for s in statuses}
        state_path.write_text(json.dumps(before), encoding="utf-8")
        units = tuple(WorkUnit(s, "offline", "T323", "2.4.0", s, "RISK", 1) for s in statuses)
        executed = []
        def executor(unit):
            executed.append(unit.work_id)
            return {"status": "COMPLETED"}
        after = BatchRunner(state_path).run(units, executor)
        check("terminal_records_preserved_exactly", all(after[s] == before[s] for s in statuses[:-1]))
        check("only_infrastructure_failure_retried", executed == ["RETRYABLE_INFRA_FAILURE"])

    actions = [{"type": "select_candidate", "status": "OK", "agent_id": "bad"}]
    oracle = {"acceptable_agents": ["good"]}
    equal = score_t353(actions, {}, oracle, paired_selection={"honest": "good", "manipulated": "good"})
    different = score_t353(actions, {}, oracle, paired_selection={"honest": "good", "manipulated": "bad"})
    check("equal_paired_choices_delta_zero_despite_unsafe_primary", equal["counterfactual_selection_delta"] == 0 and equal["outcome_class"] == "UNSAFE_ACTION")
    check("different_paired_choices_delta_one", different["counterfactual_selection_delta"] == 1)

    dataset = root / "data/datasets/T353/2.3.0/cases.jsonl"
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    case = next(c for c in cases if c["provenance"]["condition"] == "RISK")
    profile = ModelProfile("mock", "offline-corrective-validation", {"tools": True}, {})
    # Initialize the Windows Proactor loop before blocking network connections.
    with asyncio.Runner() as runner, ExitStack() as guards:
        runner.get_loop()
        for name in ("connect", "connect_ex"):
            guards.enter_context(patch.object(socket.socket, name, side_effect=AssertionError("network forbidden")))
        guards.enter_context(patch("socket.create_connection", side_effect=AssertionError("network forbidden")))
        result = runner.run(execute_construct_case(candidate, "T353", case, DiscoverySelectionBaseline("safe"), profile, run_id="offline-corrective-candidate"))
    replay = result["replay"]
    paired = replay["scenario"]["paired_runs"]
    check("both_paired_branches_retained", set(paired) == {"honest", "manipulated"})
    counts = {}
    for label, bundle in [("primary", replay), *[(mode, value.get("replay", {})) for mode, value in paired.items()]]:
        counts[label] = len(bundle.get("model_records", []))
        check(label + "_raw_model_io_present", counts[label] > 0)
        check(label + "_replay_hash_valid", bundle.get("content_sha256") == canonical_sha256({k: v for k, v in bundle.items() if k != "content_sha256"}))
        check(label + "_oracle_reference_preserved", bundle.get("oracle_refs") == [f"oracle://{case['candidate_id']}"])
        check(label + "_actions_and_world_present", bool(bundle.get("scorer_inputs", {}).get("actions")) and bool(bundle.get("world_snapshot")))
        for record in bundle.get("model_records", []):
            check(label + "_request_hash_" + record["record_id"], record["request_sha256"] == canonical_sha256(record["request"]))
    check("runtime_version_bumped", result["dispatch"]["runtime_version"] == "T353-selection-2.2.0")
    check("dispatch_version_bumped", result["dispatch"]["dispatch_version"] == "construct-dispatch-1.0.1")
    check("active_scientific_source_unchanged", source_tree_hash(root) == source_before)
    check("all_ioabench_modules_from_candidate", all(Path(m.__file__).resolve().is_relative_to(candidate) for n, m in sys.modules.items() if n.startswith("ioabench") and getattr(m, "__file__", None)))
    report = {"artifact": "ISOLATED_CORRECTIVE_CANDIDATE_VALIDATION", "pass": not failures,
              "provider_calls": 0, "formal_acceptance": False, "checks": checks, "failures": failures,
              "active_source_sha256": source_before, "candidate_source_sha256": source_tree_hash(candidate),
              "validation_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(), "case_id": case["candidate_id"],
              "model_record_counts": counts, "result": result}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"pass": report["pass"], "checks": len(checks), "failures": failures, "output": str(args.output)}))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
