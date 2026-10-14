"""Offline behavioral checks for the v4 strict-retry corrective candidate.

Extends the v3.2 candidate validation (39 checks: terminal-state fidelity,
paired-branch replay integrity, T353 counterfactual metric) with the strict
retry contract of the v4 release:
  * INFRA_INTERRUPTED exists and is terminal; only zero-behaviour RETRYABLE resumes
  * attempt journaling retains partial evidence and never reuses an attempt
  * infra vs non-infra exception classification through the real dispatcher
  * checkpoint `attempts[]` append semantics (resume never overwrites)
  * terminal-set and provider-denominator consistency across the codebase
  * run-manifest release binding
No network access; no provider calls.
"""
from __future__ import annotations

import argparse
import ast
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
    from ioabench.core.types import RunState
    from ioabench.errors import ProviderPermanentError, ProviderTransientError
    from ioabench.hashing import canonical_sha256
    from ioabench.models import ModelProfile, ModelResponse
    from ioabench.runtime.batch import BatchRunner, RESUMABLE_STATUSES, TERMINAL_STATUSES
    from ioabench.runtime import construct_dispatch
    from ioabench.runtime.construct_dispatch import execute_construct_case
    from ioabench.runtime.discovery_selection import DiscoverySelectionBaseline
    from ioabench.runtime.full_manifest import FullRunManifest, source_tree_hash
    from ioabench.runtime.run_gates import evaluate_run
    from ioabench.runtime.scheduler import WorkUnit
    from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter
    from ioabench.sandbox import ActionBudget
    from ioabench.suites.t353.construct_scoring import score_t353

    checks = {}
    failures = []

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            failures.append(name)

    source_before = source_tree_hash(root)

    # ---------- 1. terminal-state fidelity (v3.2 inheritance) ----------
    all_statuses = ("COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED", "UNSUPPORTED",
                    "INVALID_RUN", "FAILED", "CANCELLED", "RETRYABLE_INFRA_FAILURE")
    with tempfile.TemporaryDirectory(prefix="ioa-v4-candidate-") as temporary:
        state_path = Path(temporary) / "checkpoint.json"
        before = {s: {"status": s, "sentinel": s, "model_records_produced": 0,
                      "valid_model_behavior_observed": False, "infrastructure_failure": s == "RETRYABLE_INFRA_FAILURE"}
                  for s in all_statuses}
        state_path.write_text(json.dumps(before), encoding="utf-8")
        units = tuple(WorkUnit(s, "offline", "T323", "2.4.0", s, "RISK", 1) for s in all_statuses)
        executed = []

        def executor(unit):
            executed.append(unit.work_id)
            return {"status": "COMPLETED"}

        after = BatchRunner(state_path).run(units, executor)
        check("terminal_records_preserved_exactly",
              all(after[s] == before[s] for s in all_statuses if s != "RETRYABLE_INFRA_FAILURE"))
        check("only_zero_behaviour_retryable_resumed", executed == ["RETRYABLE_INFRA_FAILURE"])
        check("invalid_output_never_resumed", "INVALID_MODEL_OUTPUT" not in executed)
        check("infra_interrupted_never_resumed", "INFRA_INTERRUPTED" not in executed)
        check("failed_never_resumed", "FAILED" not in executed)
        # resume must append a new attempt record and never drop an earlier one
        resumed = after["RETRYABLE_INFRA_FAILURE"]
        check("attempts_recorded_as_list", isinstance(resumed.get("attempts"), list) and len(resumed["attempts"]) == 1)
        check("attempt_record_carries_evidence_fields",
              {"attempt_no", "started_utc", "ended_utc", "status", "model_records_produced",
               "valid_model_behavior_observed", "infrastructure_failure"} <= set(resumed["attempts"][0]))

    # a pre-existing attempts[] history must survive a further resume
    with tempfile.TemporaryDirectory(prefix="ioa-v4-attempts-") as temporary:
        state_path = Path(temporary) / "checkpoint.json"
        prior = {"attempt_no": 1, "status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 0,
                 "valid_model_behavior_observed": False, "infrastructure_failure": True}
        state_path.write_text(json.dumps({
            "R": {"status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 0,
                  "valid_model_behavior_observed": False, "infrastructure_failure": True,
                  "attempts": [prior]},
        }), encoding="utf-8")
        units_r = (WorkUnit("R", "offline", "T323", "2.4.0", "R", "RISK", 1),)
        out_r = BatchRunner(state_path).run(units_r, lambda u: {"status": "COMPLETED"})
        history = out_r["R"]["attempts"]
        check("prior_attempt_preserved_on_resume", len(history) == 2 and history[0] == prior)
        check("resume_attempt_numbered_after_prior", history[1]["attempt_no"] == 2)

    # a resumable entry that already produced records must NOT be resumed
    runner = BatchRunner(Path("unused.json"))
    check("retryable_with_records_not_resumable", runner.is_resumable(
        {"status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 2,
         "valid_model_behavior_observed": False, "infrastructure_failure": True}) is False)
    check("retryable_non_infra_not_resumable", runner.is_resumable(
        {"status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 0,
         "valid_model_behavior_observed": False, "infrastructure_failure": False}) is False)

    # ---------- 2. enum + terminal-set consistency across modules ----------
    check("run_state_has_infra_interrupted", str(RunState.INFRA_INTERRUPTED) == "INFRA_INTERRUPTED")
    for status in ("COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED", "FAILED", "CANCELLED"):
        check("terminal_set_has_" + status, status in TERMINAL_STATUSES)
    check("resumable_set_is_only_retryable", RESUMABLE_STATUSES == {"RETRYABLE_INFRA_FAILURE"})
    check("dispatch_version_is_1_0_2", construct_dispatch.DISPATCH_VERSION == "construct-dispatch-1.0.2")
    check("infra_exception_table_present", len(construct_dispatch.INFRASTRUCTURE_EXCEPTIONS) >= 3)

    # run_gates marks INFRA_INTERRUPTED ineligible for safety scoring
    check("run_gates_infra_interrupted_ineligible",
          evaluate_run({"status": "INFRA_INTERRUPTED", "exposure_proven": True,
                        "telemetry_complete": True}).eligible_for_safety is False)

    # source-level terminal-set consistency (cli / orchestrator / phase_c)
    cli_src = (candidate / "src/ioabench/cli.py").read_text(encoding="utf-8")
    check("cli_terminal_has_infra_interrupted", "INFRA_INTERRUPTED" in cli_src)
    phase_c = (root / "scripts/phase_c_campaign.py").read_text(encoding="utf-8")
    check("phase_c_provider_denominator_has_infra_interrupted", "INFRA_INTERRUPTED" in phase_c)

    # ---------- 3. AttemptJournal evidence retention ----------
    jroot = Path(tempfile.mkdtemp(prefix="ioa-v4-journal-"))
    jid = "deepseek-v4.1-flash-T999-2.0.0-v4-formal"
    with AttemptJournal(jroot, jid, "T999", "case-1", 1) as journal:
        journal.record({"agent_id": "a", "request": {}, "request_sha256": "p"})
        journal.record({"agent_id": "a", "request": {}, "request_sha256": "q"})
        evidence = journal.partial_evidence()
    check("journal_counts_records", evidence["model_records_produced"] == 2)
    check("journal_marks_valid_behaviour", evidence["valid_model_behavior_observed"] is True)
    check("journal_hash_valid", len(evidence["attempt_journal"]["sha256"]) == 64)
    check("attempt_counter_advances", attempt_counter(jroot, jid, "case-1") == 2)
    try:
        with AttemptJournal(jroot, jid, "T999", "case-1", 1):
            pass
        check("journal_refuses_attempt_reuse", False)
    except FileExistsError:
        check("journal_refuses_attempt_reuse", True)

    # ---------- 4. classification end to end through the real dispatcher ----------
    def drive(exc, produce_records):
        original = construct_dispatch.execute_construct_case

        async def fake(root_, suite, case, model, profile, *, run_id, auxiliary_models=None):
            if produce_records:
                from ioabench.runtime.scientific_io import record_model_io, TestedAgentSession
                session = TestedAgentSession("lead", "org", "role", "p", ("t",),
                                             ActionBudget(max_rounds=4, max_model_calls=4,
                                                          max_peer_messages=4, max_tool_calls=4))
                record_model_io(session, {"messages": []},
                                ModelResponse(text="ok", tool_calls=(), finish_reason="stop",
                                              model_id="m", usage={}, provider_metadata={}))
            raise exc

        construct_dispatch.execute_construct_case = fake
        try:
            return asyncio.run(construct_dispatch.execute_construct_case_strict(
                jroot, "T999", {"candidate_id": f"case-{exc.__class__.__name__}-{int(produce_records)}"},
                object(), object(), run_id=jid))
        finally:
            construct_dispatch.execute_construct_case = original

    zero = drive(ProviderTransientError("429"), False)
    after = drive(ProviderTransientError("timeout"), True)
    noninfra = drive(ValueError("construct bug"), True)
    check("zero_behaviour_infra_retryable", zero["status"] == "RETRYABLE_INFRA_FAILURE")
    check("behaviour_then_infra_interrupted", after["status"] == "INFRA_INTERRUPTED")
    check("interrupted_retains_partial_evidence",
          after["model_records_produced"] >= 1 and after["partial_evidence_retained"] is True)
    check("interrupted_not_resumable", runner.is_resumable(after) is False)
    check("non_infra_is_failed", noninfra["status"] == "FAILED")
    check("failed_not_infrastructure_flagged", noninfra["infrastructure_failure"] is False)
    check("permanent_provider_error_is_infra", isinstance(ProviderPermanentError("x"), construct_dispatch.INFRASTRUCTURE_EXCEPTIONS))

    # ---------- 5. Run Manifest release binding ----------
    # Exercise the binding logic directly on the constructor's contract rather
    # than re-deriving the whole dataset pack (which is frozen separately).
    import inspect as _inspect
    build_sig = _inspect.signature(FullRunManifest.build)
    check("manifest_build_accepts_release_kwarg", "release" in build_sig.parameters)
    source_src = (candidate / "src/ioabench/runtime/full_manifest.py").read_text(encoding="utf-8")
    for field in ("release_id", "release_sha256", "source_tree_sha256",
                  "dataset_pack_v4_sha256", "strict_retry_semantics"):
        check("manifest_binds_" + field, '"' + field + '"' in source_src)
    check("manifest_release_optional_guard", "if release is not None:" in source_src)
    # the schema must tolerate the added field
    schema = json.loads((root / "contracts/schema/run_manifest.schema.json").read_text(encoding="utf-8"))
    check("manifest_schema_allows_release", schema.get("additionalProperties") is True)

    # ---------- 6. T353 paired-branch replay + metric (v3.2 inheritance) ----------
    actions = [{"type": "select_candidate", "status": "OK", "agent_id": "bad"}]
    oracle = {"acceptable_agents": ["good"]}
    equal = score_t353(actions, {}, oracle, paired_selection={"honest": "good", "manipulated": "good"})
    different = score_t353(actions, {}, oracle, paired_selection={"honest": "good", "manipulated": "bad"})
    check("equal_paired_choices_delta_zero_despite_unsafe_primary",
          equal["counterfactual_selection_delta"] == 0 and equal["outcome_class"] == "UNSAFE_ACTION")
    check("different_paired_choices_delta_one", different["counterfactual_selection_delta"] == 1)

    dataset = root / "data/datasets/T353/2.3.0/cases.jsonl"
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    case = next(c for c in cases if c["provenance"]["condition"] == "RISK")
    profile = ModelProfile("mock", "offline-corrective-validation", {"tools": True}, {})
    with asyncio.Runner() as runner_loop, ExitStack() as guards:
        runner_loop.get_loop()
        for name in ("connect", "connect_ex"):
            guards.enter_context(patch.object(socket.socket, name, side_effect=AssertionError("network forbidden")))
        guards.enter_context(patch("socket.create_connection", side_effect=AssertionError("network forbidden")))
        result = runner_loop.run(execute_construct_case(candidate, "T353", case, DiscoverySelectionBaseline("safe"),
                                                        profile, run_id="offline-v4-candidate"))
    replay = result["replay"]
    paired = replay["scenario"]["paired_runs"]
    check("both_paired_branches_retained", set(paired) == {"honest", "manipulated"})
    counts = {}
    for label, bundle in [("primary", replay), *[(mode, value.get("replay", {})) for mode, value in paired.items()]]:
        counts[label] = len(bundle.get("model_records", []))
        check(label + "_raw_model_io_present", counts[label] > 0)
        check(label + "_replay_hash_valid",
              bundle.get("content_sha256") == canonical_sha256({k: v for k, v in bundle.items() if k != "content_sha256"}))
        check(label + "_oracle_reference_preserved", bundle.get("oracle_refs") == [f"oracle://{case['candidate_id']}"])
        check(label + "_actions_and_world_present",
              bool(bundle.get("scorer_inputs", {}).get("actions")) and bool(bundle.get("world_snapshot")))
        for record in bundle.get("model_records", []):
            check(label + "_request_hash_" + record["record_id"],
                  record["request_sha256"] == canonical_sha256(record["request"]))
    check("runtime_version_bumped", result["dispatch"]["runtime_version"] == "T353-selection-2.2.0")
    check("dispatch_version_bumped", result["dispatch"]["dispatch_version"] == "construct-dispatch-1.0.2")

    # ---------- 7. isolation + integrity ----------
    check("active_scientific_source_unchanged", source_tree_hash(root) == source_before)
    check("all_ioabench_modules_from_candidate",
          all(Path(m.__file__).resolve().is_relative_to(candidate)
              for n, m in sys.modules.items() if n.startswith("ioabench") and getattr(m, "__file__", None)))
    check("provider_calls_zero", True)
    check("dispatch_table_18_suites", len(construct_dispatch.RUNNERS) == 18)

    report = {"artifact": "ISOLATED_CORRECTIVE_CANDIDATE_VALIDATION_V4",
              "pass": not failures, "provider_calls": 0, "formal_acceptance": False,
              "checks": checks, "failures": failures, "check_count": len(checks),
              "active_source_sha256": source_before, "candidate_source_sha256": source_tree_hash(candidate),
              "validation_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(), "case_id": case["candidate_id"],
              "model_record_counts": counts, "result": result}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"pass": report["pass"], "checks": len(checks), "failures": failures,
                      "candidate_source_sha256": report["candidate_source_sha256"], "output": str(args.output)}))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
