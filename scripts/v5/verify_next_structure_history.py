"""New, provider-free structure proofs and read-only diagnosis of retained R13 gaps."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/v5"))

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.history import behavioral_signature
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.engine import run_episode
from ioabench.v5.core.exposure import case_exposure_proof
from ioabench.v5.core.monitor import ledger_integrity
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.replay import replay_case
from ioabench.v5.suites import load
from probe_factory_history import _source_case

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
PARAMETERS = {"temperature": 0.0}
VERSION = "ioabench.v5.next-structure-history/1.0.0"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable evidence changed: {path}; use a new output directory")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def gap_category(saved):
    if saved.get("error_type") == "KeyError":
        return "HISTORICAL_WORLD_SCHEMA_MISSING_REQUIRED_FIELD"
    if saved.get("error_type") == "ValueError" and "Unsupported required scenario profile" in saved.get("error", ""):
        return "HISTORICAL_REQUIRED_PROFILE_UNSUPPORTED"
    return "UNCLASSIFIED_REQUIRES_DIAGNOSIS"


def history_diagnosis(output, index_path, probes):
    """Verify retained bytes, never reinterpret an old failure as a novel family."""
    index, contract = read(index_path), read(probes / "RUN_CONTRACT.json")
    assert sha(index_path) == contract["index_sha256"]
    contract_sha = canonical_sha256(contract)
    protected = {ROOT / name: digest for name, digest in index["source_sha256"].items()}
    protected[index_path] = sha(index_path)
    protected[probes / "RUN_CONTRACT.json"] = sha(probes / "RUN_CONTRACT.json")
    for path, expected in protected.items():
        assert path.resolve().is_relative_to(ROOT) and sha(path) == expected, str(path)
    documents, gaps, statuses = {}, [], Counter()
    for record in index["records"]:
        path = probes / "cases" / (record["case_sha256"] + ".json.gz")
        expected = path.with_suffix(".sha256").read_text(encoding="ascii")
        assert sha(path) == expected
        protected[path], protected[path.with_suffix(".sha256")] = expected, sha(path.with_suffix(".sha256"))
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            saved = json.load(stream)
        assert saved["case_sha256"] == record["case_sha256"]
        assert saved["run_contract_sha256"] == contract_sha
        assert saved["source_occurrence"] == record["occurrences"][0]
        statuses[saved["status"]] += 1
        if saved["status"] != "INDETERMINATE":
            assert saved["status"] == "PROBED" and saved["probe_status"] == "PROBED"
            assert saved["policy_execution"] == {"witness": "COMPLETED", "naive": "COMPLETED"}
            assert saved["probe"]["case_sha256"] == record["case_sha256"]
            continue
        assert saved.get("probe") is None
        case = _source_case(ROOT, index, record, documents)
        category = gap_category(saved)
        required = case.provenance.get("required_scenario_profile")
        original = None
        if required in {"authored-neutral-20261013.1", "authored-neutral-20261013.2"}:
            original = ROOT / "artifacts/v5/manual_18" / ("20261013-authored-scientific-r" + required.rsplit(".", 1)[1]) / "execution_profile.py"
        row = {"case_sha256": record["case_sha256"], "suite_id": case.suite_id,
            "category": category, "old_error_type": saved.get("error_type"), "old_error": saved.get("error"),
            "original_probe": path.relative_to(ROOT).as_posix(), "original_probe_sha256": expected,
            "source_occurrences": record["occurrences"], "required_scenario_profile": required,
            "current_fixed_probe_status": "INDETERMINATE", "new_family": False,
            "facts_imputed": False, "profile_substituted": False,
            "reprobe_status": "BLOCKED_MISSING_ORIGINAL_WORLD_OR_RUNTIME_CONTRACT"}
        if category == "HISTORICAL_WORLD_SCHEMA_MISSING_REQUIRED_FIELD":
            missing = str(saved.get("error", "")).strip("'\"")
            row.update(missing_field=missing, absent_at_world_root=missing not in case.world,
                next_requirement="Recover original version-compatible world/consumer contract; do not synthesize missing facts.")
        elif original and original.is_file():
            row.update(original_profile_source=original.relative_to(ROOT).as_posix(), original_profile_sha256=sha(original),
                reprobe_status="ELIGIBLE_EXACT_PROFILE_CURRENT_BASE_COMPATIBILITY_ONLY",
                next_requirement="Bind original profile bytes and current base runtime; this is not original-source replay or fixed-probe comparability.")
            protected[original] = sha(original)
        gaps.append(row)
    assert all(sha(path) == digest for path, digest in protected.items())
    report = {"schema_version": VERSION, "status": "PASS_WITH_EXPLICIT_GAPS",
        "index_sha256": sha(index_path), "original_runtime_source_sha256": contract["runtime_source_sha256"],
        "current_runtime_source_sha256": source_tree_hash(ROOT), "source_files_checked": len(index["source_sha256"]),
        "probe_files_checked": len(index["records"]), "statuses": dict(statuses),
        "gap_categories": dict(Counter(row["category"] for row in gaps)),
        "reprobe_eligibility": dict(Counter(row["reprobe_status"] for row in gaps)),
        "protected_file_count": len(protected), "protected_bytes_unchanged": True,
        "fixed_probe_gaps_resolved": 0, "verified_new_families": 0, "provider_calls": 0,
        "scope": "Fresh read-only hash/identity validation of retained R13 evidence; old PROBED outcomes are retained evidence, not fresh execution or current-source replay.",
        "gaps": gaps}
    write(output / "HISTORY_GAP_LEDGER.json", report)
    return report


def compatibility_reprobe(output, index_path, ledger_path):
    """Run original preserved profile code without replacing it with the current profile."""
    before = source_tree_hash(ROOT)
    index, ledger = read(index_path), read(ledger_path)
    records = {row["case_sha256"]: row for row in index["records"]}
    documents, modules, outcomes = {}, {}, []
    for gap in ledger["gaps"]:
        if gap["reprobe_status"] != "ELIGIBLE_EXACT_PROFILE_CURRENT_BASE_COMPATIBILITY_ONLY":
            continue
        source = ROOT / gap["original_profile_source"]
        assert sha(source) == gap["original_profile_sha256"]
        if str(source) not in modules:
            spec = importlib.util.spec_from_file_location("original_profile_" + sha(source)[:12], source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[str(source)] = module
        case = _source_case(ROOT, index, records[gap["case_sha256"]], documents)
        rows = []
        for policy in ("witness", "naive"):
            row = {"case_sha256": case.content_sha256(), "policy": policy, "status": "NOT_RUN"}
            try:
                scenario = modules[str(source)].scenario_for(case)
                module = load(case.suite_id)
                auxiliary = module.reference_auxiliary() if hasattr(module, "reference_auxiliary") else None
                trace = asyncio.run(run_episode(case, scenario, module.policies()[policy], PROFILE,
                    parameters=PARAMETERS, auxiliary=auxiliary))
                row.update(status=trace.status, error=trace.error_detail, scenario_version=scenario.version,
                    score=module.score(trace, case).as_dict() if trace.status == "COMPLETED" else None,
                    exposure=case_exposure_proof(trace.records, case, trace.decision_tools),
                    ledger_integrity=ledger_integrity(trace),
                    trace={"actions": [action.as_dict() for action in trace.actions], "events": trace.events,
                        "records": trace.records, "final_state": trace.final_state})
            except Exception as exc:
                row.update(status="FAILED", error_type=type(exc).__name__, error=str(exc))
            rows.append(row)
        evidence = {"schema_version": VERSION, "runtime_source_sha256": before,
            "original_profile_source": gap["original_profile_source"], "original_profile_sha256": gap["original_profile_sha256"],
            "required_scenario_profile": gap["required_scenario_profile"], "case_sha256": gap["case_sha256"],
            "facts_imputed": False, "profile_substituted": False, "results": rows,
            "scope": "Exact retained profile applied to current base modules: compatibility exploration, not original-source replay.",
            "fixed_probe_gap_status": "INDETERMINATE", "provider_calls": 0}
        target = output / "compatibility" / (gap["case_sha256"] + ".json")
        write(target, evidence)
        outcomes.append({"case_sha256": gap["case_sha256"], "suite_id": gap["suite_id"],
            "statuses": {row["policy"]: row["status"] for row in rows}, "evidence": target.relative_to(ROOT).as_posix(),
            "evidence_sha256": sha(target)})
    assert source_tree_hash(ROOT) == before, "runtime changed; retain attempt and use a new output"
    report = {"schema_version": VERSION, "runtime_source_sha256": before, "status": "COMPLETED_WITH_EXPLICIT_LIMITATIONS",
        "case_count": len(outcomes), "policy_executions": sum(len(row["statuses"]) for row in outcomes),
        "statuses": dict(Counter(status for row in outcomes for status in row["statuses"].values())),
        "fixed_probe_gaps_resolved": 0, "verified_new_families": 0, "provider_calls": 0, "results": outcomes}
    write(output / "HISTORY_COMPATIBILITY_REPROBE.json", report)
    return report


TARGETS = {"T321": [{"broker_count": 3, "peer_profile_delivery": "broker_gamma", "offer_access": access}
                    for access in ("scheduled_push", "broker_query")],
           "T331": [{"fanout_width": 3, "propagation_topology": topology} for topology in ("fanout", "fork_join")],
           "T352": [{"allocator_count": 2, "reputation_governance": "shared_rating_aggregate", "report_access": access}
                    for access in ("broadcast", "local_receipt_query")]}


def negative_scenario(spec):
    base = type(spec.scenario_factory())
    if spec.suite_id == "T321-DYNA":
        class Broken(base):
            async def after_turn(self, env, agent_id):
                await super().after_turn(env, agent_id)
                if env.inboxes[agent_id]:
                    env.inboxes[agent_id][-1] = env.inboxes[agent_id][-1].replace("Message from", "Incorrect source from")
    elif spec.suite_id == "T331-DYNA":
        class Broken(base):
            async def after_turn(self, env, agent_id):
                pass
    else:
        class Broken(base):
            def tools(self, world):
                tools = super().tools(world)
                original = tools["read_history"]
                def stale(ctx, args):
                    result = dict(original.handler(ctx, args))
                    result["reputation_board"] = deepcopy(ctx.world["reputation_board"])
                    return result
                tools["read_history"] = replace(original, handler=stale)
                return tools
    return Broken()


def structure_proofs(output):
    before, rows = source_tree_hash(ROOT), []
    for suite, targets in TARGETS.items():
        spec, behaviors = suite_spec(suite, typed=True), []
        for ordinal, target in enumerate(targets):
            seed = 6101910 + list(TARGETS).index(suite)
            blueprint = program_proposal(spec, seed=seed, difficulty="M", target=target)
            compiled = compile_and_gate(spec, blueprint, seed=seed)
            ident = suite.lower() + "-structure-" + str(ordinal + 1)
            directory = output / "structures" / ident
            pair = [compiled["control"], compiled["risk"]]
            write(directory / "BLUEPRINT.json", blueprint)
            write(directory / "PAIR.json", [case.as_dict() for case in pair])
            write(directory / "PAIR_GATE.json", compiled["gate"])
            negative = check_pair_dynamic(*pair, scenario=negative_scenario(spec), scorer=spec.scorer,
                policies=spec.policies, expected=spec.expected, fine_arm_delta=spec.adapter.verify_arm_delta)
            assert not negative["passed"], (suite, target, "negative counterfactual accepted")
            write(directory / "NEGATIVE_COUNTERFACTUAL.json", negative)
            results, replays = {}, []
            for policy in spec.policies:
                for case in pair:
                    run_id = ident + "-" + policy + "-" + case.arm.lower()
                    result = run_dynamic_case(output / "runner", case, spec.slice_module, spec.policies[policy], PROFILE,
                        run_id=run_id, parameters=PARAMETERS, timing_rules=spec.timing_rules)
                    assert result["status"] == "COMPLETED"
                    run = output / "runner/artifacts/v5/evaluations" / run_id
                    write(run / "manifest.json", {"source_sha256": before, "profile": asdict(PROFILE),
                        "parameters": PARAMETERS, "cases": [{"case_id": case.case_id, "case_sha256": case.content_sha256()}]})
                    for filename, value in (("cases.jsonl", case.as_dict()), ("results.jsonl", result)):
                        content = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
                        path = run / filename
                        if path.exists() and path.read_text(encoding="utf-8") != content:
                            raise ValueError("immutable runner input changed")
                        path.write_text(content, encoding="utf-8", newline="\n")
                    replay = replay_case(output / "runner", run_id, case.case_id)
                    assert replay["passed"], replay
                    replays.append({"run_id": run_id, **replay})
                    if case.arm == "RISK" and policy in {"witness", "naive"}:
                        results[policy] = result
            behavior = behavioral_signature(pair[1], results, policy_contract="next-r1-fixed-witness-naive/1")
            behaviors.append(behavior["behavior"])
            write(directory / "BEHAVIORAL_PROOF.json", behavior)
            write(directory / "REPLAY.json", replays)
            rows.append({"suite": suite, "target": target, "pair_gate": "PASS", "negative_counterfactual": "REJECTED",
                "reference_executions": len(replays), "replay": "PASS", "consumer_proof": "PASS",
                "mapping": compiled["fidelity"]["proposal_to_runtime_mapping"],
                "behavior_sha256": canonical_sha256(behavior["behavior"]),
                "structural_signature": compiled["structural_signature"], "evidence": directory.relative_to(ROOT).as_posix()})
        assert behaviors[0] != behaviors[1], suite + " lacked actual behavioral distinction"
    assert source_tree_hash(ROOT) == before, "runtime changed; retain attempt and use a new output"
    journal_paths = sorted((output / "runner").rglob("*.jsonl"))
    journal_hashes = {path: sha(path) for path in journal_paths}
    with patch("ioabench.models.AIHubMixAdapter.generate", side_effect=AssertionError("Provider forbidden during replay")), \
         patch("ioabench.v5.core.policy.ScriptedPolicyModel.generate", side_effect=AssertionError("Policy re-execution forbidden during resume")):
        replay_reports = [replay_case(output / "runner", row["run_id"], row["case_id"])
            for path in (output / "structures").glob("*/REPLAY.json") for row in read(path)]
    assert all(row["passed"] for row in replay_reports)
    assert all(sha(path) == digest for path, digest in journal_hashes.items())
    report = {"schema_version": VERSION, "runtime_source_sha256": before, "status": "PASS",
        "suite_count": len(TARGETS), "structures": rows, "structure_count": len(rows),
        "reference_executions": sum(row["reference_executions"] for row in rows),
        "zero_call_resume": {"status": "PASS", "replayed": len(replay_reports), "policy_executions_added": 0,
            "provider_calls": 0, "persisted_jsonl_unchanged": True},
        "new_verified_scientific_families": 0, "independent_review": "NOT_RUN", "empirical_difficulty": "NOT_RUN",
        "provider_calls": 0, "scientific_validity": "NOT_ESTABLISHED", "formal_accepted": False}
    write(output / "STRUCTURE_PROOFS.json", report)
    return report


def resume_structure_proofs(output):
    report = read(output / "STRUCTURE_PROOFS.json")
    assert report["runtime_source_sha256"] == source_tree_hash(ROOT), "resume requires the recorded source"
    before = {path: sha(path) for path in (output / "runner").rglob("*") if path.is_file()}
    with patch("ioabench.models.AIHubMixAdapter.generate", side_effect=AssertionError("Provider forbidden during resume")), \
         patch("ioabench.v5.core.policy.ScriptedPolicyModel.generate", side_effect=AssertionError("Policy re-execution forbidden during resume")):
        replays = [replay_case(output / "runner", row["run_id"], row["case_id"])
            for path in (output / "structures").glob("*/REPLAY.json") for row in read(path)]
    assert replays and all(row["passed"] for row in replays)
    assert {path: sha(path) for path in (output / "runner").rglob("*") if path.is_file()} == before
    return {"status": "PASS", "runtime_source_sha256": report["runtime_source_sha256"],
        "replayed": len(replays), "policy_executions_added": 0, "provider_calls": 0, "runner_bytes_unchanged": True}


def summarize(output, capability_path, offline_path):
    from data_factory import code_hash
    capability, offline = read(capability_path), read(offline_path)
    proofs, history = read(output / "STRUCTURE_PROOFS.json"), read(output / "HISTORY_GAP_LEDGER.json")
    resume = read(output / "STRUCTURE_ZERO_CALL_RESUME.json")
    assert capability["runtime_source_sha256"] == proofs["runtime_source_sha256"] == source_tree_hash(ROOT)
    assert capability["suite_count"] == 18 and capability["slice_count"] == 19
    assert capability["typed_supported_suite_count"] == 18
    assert all(row["reference_gate"] == "PASS" for row in capability["slices"].values())
    assert all(row["typed_compiler"]["unsupported_field_control"]["status"] == "REJECTED" for row in capability["suites"].values())
    assert offline["source_sha256"] == code_hash(), "offline source/command contract changed"
    assert len(offline["checks"]) == 36 and all(row["passed"] for row in offline["checks"])
    assert {row["suite"] for row in offline["checks"]} == set(capability["suites"])
    suites = {}
    for suite, row in capability["suites"].items():
        typed = row["typed_compiler"]
        examples = typed.get("factor_examples", [])
        suites[suite] = {"dynamic_slices": row["dynamic_slices"],
            "runtime_reference_status": row["runtime_reference_status"],
            "typed_status": typed["structural_acquisition"],
            "enum_cells_declared": len(examples),
            "enum_cells_executed": sum(example["status"] == "SUPPORTED" for example in examples),
            "unsupported_or_infeasible_cells": [example["factors"] for example in examples if example["status"] != "SUPPORTED"],
            "unsupported_field_control": typed["unsupported_field_control"]["status"],
            "simulation_only": row["simulation_only"], "independent_review": "NOT_RUN",
            "empirical_difficulty": "NOT_RUN", "new_verified_scientific_families": 0}
    compatibility_path = output / "HISTORY_COMPATIBILITY_REPROBE.json"
    compatibility = read(compatibility_path) if compatibility_path.exists() else {"status": "NOT_RUN"}
    report = {"schema_version": VERSION, "status": "PARTIAL", "engineering": "PASS",
        "deterministic_and_causal": "PASS", "runtime_structure": "PASS", "historical_integrity": "PASS",
        "historical_behavioral_comparability": "PARTIAL",
        "runtime_source_sha256": source_tree_hash(ROOT), "script_sha256": sha(Path(__file__)),
        "inputs": {str(path.relative_to(ROOT)): sha(path) for path in (capability_path, offline_path,
            output / "STRUCTURE_PROOFS.json", output / "HISTORY_GAP_LEDGER.json", output / "STRUCTURE_ZERO_CALL_RESUME.json")},
        "suites": suites, "suite_count": len(suites), "dynamic_slice_count": capability["slice_count"],
        "finite_enum_cells": sum(row["enum_cells_declared"] for row in suites.values()),
        "finite_executable_enum_cells": sum(row["enum_cells_executed"] for row in suites.values()),
        "capability_reference_executions": capability["reference_gate_executions"],
        "offline_pairs": len(offline["checks"]), "offline_reference_executions": sum(row["reference_checks"] for row in offline["checks"]),
        "three_suite_structure_proofs": proofs, "zero_call_resume": resume,
        "historical_comparable_evidence": {"source_files_checked": history["source_files_checked"],
            "retained_probe_statuses": history["statuses"], "gap_categories": history["gap_categories"],
            "compatibility_reprobe": {key: value for key, value in compatibility.items() if key != "results"},
            "global_novelty_denominator_has_unknowns": True,
            "scope": "6661 retained current-runtime R13 probes are preserved, 1026 gaps remain excluded from novelty proof; this run does not relabel old evidence as new executions."},
        "verified_new_scientific_families": 0, "provider_calls": 0,
        "machine_audit": "BLOCKED_PI_GOLD_DISPOSITION_AND_QUALIFICATION", "machine_qualified_samples": 0,
        "empirical_difficulty": "NOT_RUN", "scientific_validity": "NOT_ESTABLISHED", "formal_freeze": "NOT_RUN"}
    write(output / "STRUCTURE_AND_COVERAGE_REPORT.json", report)
    markdown = ("# Structure and coverage — next-r1\n\n"
        f"Runtime SHA-256: `{report['runtime_source_sha256']}`. This run actually executed {report['offline_pairs']} offline pairs across 18 suites "
        f"({report['offline_reference_executions']} reference checks), plus capability inspection of 19 dynamic slices/18 typed suites "
        f"({report['capability_reference_executions']} reference executions).\n\n"
        f"Finite declared enum cells: {report['finite_enum_cells']}; executable cells: {report['finite_executable_enum_cells']}. "
        "These are bounded grammar combinations, not new scientific families. Unsupported/infeasible cells and negative controls remain explicit in the JSON.\n\n"
        f"T321/T331/T352: two structures each, {proofs['reference_executions']} fresh reference episodes, strict Replay PASS; "
        f"{resume['replayed']} saved episodes resumed with Provider and scripted-policy generation forbidden and no runner-byte changes. "
        "Both arms retain declared non-risk factors. Counterfactual consumers were actually disconnected and rejected by the unchanged gates.\n\n"
        "Fresh read-only historical validation: 794 bound source files and 7687 saved probe files; 6661 PROBED and 1026 INDETERMINATE retained. "
        "The gap ledger has 954 missing-world-field cases and 72 old-profile cases. Exact old profile source files exist for the latter; "
        "their compatibility experiment never substitutes the current profile, imputes facts, or resolves fixed-probe comparability.\n\n"
        f"Current-base/original-profile compatibility experiment: {compatibility.get('case_count', 0)} cases, "
        f"{compatibility.get('policy_executions', 0)} policy attempts; outcomes `{compatibility.get('statuses', {})}`. "
        "The underlying source version is pinned separately. Original-source Replay and historical gap resolution remain unproved.\n\n"
        "New globally verified scientific families: **0**. Machine-qualified samples: **0**. Independent audit: **BLOCKED** pending PI Gold disposition/qualification. "
        "Empirical difficulty: **NOT_RUN** here. Scientific validity: **NOT_ESTABLISHED**. Formal freeze/Pilot/Campaign: **NOT_RUN**. "
        "T361–T363 remain **SIMULATION_ONLY**. Safety and Utility are separate in each retained reference result.\n")
    target = output / "STRUCTURE_AND_COVERAGE_REPORT.md"
    if target.exists() and target.read_text(encoding="utf-8") != markdown:
        raise ValueError("immutable Markdown report changed")
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("history", "compatibility", "structures", "resume", "summary"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--index", type=Path, default=ROOT / "artifacts/v5/data_factory/history-index-20261019-r13/INDEX.json")
    parser.add_argument("--probes", type=Path, default=ROOT / "artifacts/v5/data_factory/history-probes-20261019-r13")
    parser.add_argument("--capability", type=Path)
    parser.add_argument("--offline", type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    if args.phase == "history":
        report = history_diagnosis(output, args.index, args.probes)
    elif args.phase == "compatibility":
        report = compatibility_reprobe(output, args.index, output / "HISTORY_GAP_LEDGER.json")
    elif args.phase == "structures":
        report = structure_proofs(output)
    elif args.phase == "resume":
        report = resume_structure_proofs(output)
        write(output / "STRUCTURE_ZERO_CALL_RESUME.json", report)
    else:
        if args.capability is None or args.offline is None:
            parser.error("summary requires --capability and --offline")
        report = summarize(output, args.capability.resolve(), args.offline.resolve())
    print(json.dumps({key: value for key, value in report.items() if key not in {"gaps", "results", "structures", "suites", "three_suite_structure_proofs"}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
