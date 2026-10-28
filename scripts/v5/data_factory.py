"""Shared data-factory preflight and bounded experimental trials. No bulk production/freeze."""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import os
import sys
import zipfile
from copy import deepcopy
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.factory import FACTORY_VERSION, prepare_models, run_candidate, recover_generation, read_json, event, validate_saved_result, write_trial_report
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.ai_generation.quality import classify_candidate
from ioabench.v5.core.case import SUITES, case_from_dict
from ioabench.v5.evaluation import atomic_json, read_cases, safe_id
from ioabench.generation.coverage import CoveragePlanner
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryRouter, qualified_contracts, engineering_contracts
from routed_t321_data_factory_s1 import _lock, _load_api_key

RUNS = ROOT / "artifacts/v5/data_factory/trials"
HISTORICAL_VERSION = "5.1.5-candidate-20261006"
T332_REPAIRED_VERSION = "5.1.6-candidate-20261009"


def historical_paths(suite_id: str) -> list[Path]:
    suite = suite_id.split("-")[0]
    versions = [HISTORICAL_VERSION]
    if suite == "T332":
        versions.append(T332_REPAIRED_VERSION)
    return [ROOT / "data/v5/datasets" / suite / version / "cases.jsonl" for version in versions]


def baseline_sources(suites: list[str]) -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for suite in suites for path in historical_paths(suite)}


def baseline_cases(spec, run_id: str, prior_candidates: int = 0):
    cases = [control for control, _ in spec.slice_module.generate(seed=0, families=3)]
    for path in historical_paths(spec.suite_id):
        cases.extend(case for case in read_cases(path) if case.arm == "CONTROL")
    for result_path in sorted(RUNS.glob("*/candidate-*/RESULT.json")):
        if (result_path.parent.parent.name == run_id
                and int(result_path.parent.name.rsplit("-", 1)[1]) > prior_candidates):
            continue
        result = read_json(result_path)
        if (result.get("status") == "MACHINE_ACCEPTED"
                and result.get("suite_id", "").split("-")[0] == spec.suite_id.split("-")[0]):
            validate_saved_result(result_path.parent, result)
            cases.append(case_from_dict(read_json(result_path.parent / "PAIR.json")[0], allow_dynamic=True))
    return cases


def save_baselines(directory: Path, pools, sources):
    atomic_json(directory / "BASELINES.json", pools)
    atomic_json(directory / "BASELINE_SOURCES.json", sources)
    atomic_json(directory / "BASELINE_MANIFEST.json", {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("BASELINES.json", "BASELINE_SOURCES.json")})


def load_baselines(directory: Path, suites: list[str]):
    path = directory / "BASELINE_MANIFEST.json"
    if not path.is_file():
        raise ValueError("baseline manifest missing; preserve this run and use a new run id")
    manifest = read_json(path)
    if not isinstance(manifest, dict) or set(manifest) != {"BASELINES.json", "BASELINE_SOURCES.json"}:
        raise ValueError("baseline manifest must bind the pool and its historical sources")
    for name, expected in manifest.items():
        if not (directory / name).is_file() or hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"baseline evidence changed: {name}")
    if baseline_sources(suites) != read_json(directory / "BASELINE_SOURCES.json"):
        raise ValueError("historical baseline sources changed; preserve this run and use a new run id")
    return read_json(directory / "BASELINES.json")


def code_hash():
    return canonical_sha256({"source": source_tree_hash(ROOT), "command": Path(__file__).read_text(encoding="utf-8")})


def extend_history(index, paths):
    """Retain pinned archive/probe bindings when adding earlier attempts in this run."""
    from ioabench.v5.ai_generation.history import build_index
    merged = deepcopy(index)
    addition = build_index(ROOT, sources=paths)
    for path in paths:
        proof_path = path.parent / "BEHAVIORAL_PROBES.json"
        if proof_path.is_file():
            validate_saved_result(path.parent, read_json(path.parent / "RESULT.json"))
            proof = read_json(proof_path)
            if proof["reference_results_sha256"] != hashlib.sha256((path.parent / "REFERENCE_RESULTS.json").read_bytes()).hexdigest():
                raise ValueError("batch behavioral probes changed")
            for record in addition["records"]:
                probe = proof["by_case_sha256"].get(record["case_sha256"])
                if probe:
                    record["behavioral_probe_signature"] = probe
            addition["source_sha256"][proof_path.relative_to(ROOT).as_posix()] = hashlib.sha256(proof_path.read_bytes()).hexdigest()
    for name, digest in addition["source_sha256"].items():
        if name in merged["source_sha256"] and merged["source_sha256"][name] != digest:
            raise ValueError(f"pinned historical source changed: {name}")
    records = {row["case_sha256"]: row for row in merged["records"]}
    for row in addition["records"]:
        if row["case_sha256"] in records:
            prior = records[row["case_sha256"]]
            prior["occurrences"].extend(item for item in row["occurrences"] if item not in prior["occurrences"])
            if prior.get("behavioral_probe_signature") is None:
                prior["behavioral_probe_signature"] = row.get("behavioral_probe_signature")
            elif row.get("behavioral_probe_signature") is not None:
                # Independent runs have distinct result hashes; keep the original pinned proof.
                old_probe = {key: value for key, value in prior["behavioral_probe_signature"].items()
                             if key != "evidence_sha256"}
                new_probe = {key: value for key, value in row["behavioral_probe_signature"].items()
                             if key != "evidence_sha256"}
                if old_probe != new_probe:
                    raise ValueError("conflicting pinned behavioral probes for the same historical case")
        else:
            records[row["case_sha256"]] = row
    merged["records"] = list(records.values())
    merged["source_sha256"].update(addition["source_sha256"])
    merged["discovered_sources"] = sorted(set(merged["discovered_sources"] + addition["discovered_sources"]))
    merged["findings"].extend(row for row in addition["findings"] if row not in merged["findings"])
    merged["sources_without_cases"] = sorted(set(merged["sources_without_cases"] + addition["sources_without_cases"]))
    merged["summary"].update(sources=len(merged["source_sha256"]), unique_cases=len(records),
        occurrences=sum(len(row["occurrences"]) for row in records.values()),
        occurrence_statuses=dict(Counter(item["status"] for row in records.values() for item in row["occurrences"])))
    return merged


def prescreen_history_targets(spec, plan, index, *, seed, directory, diversity_target="new_structure",
                              parent=None, difficulty="M"):
    """Avoid paid structural proposals for combinations already present in history."""
    from ioabench.v5.ai_generation.history import classify
    planner = CoveragePlanner()
    if diversity_target == "family_instance" and parent is None:
        return planner.next_target(plan)
    if diversity_target not in {"new_structure", "family_instance"}:
        raise ValueError("unknown diversity target")
    while selected := planner.next_target(plan):
        try:
            proposal = program_proposal(spec, seed=seed, difficulty=difficulty,
                                        target=selected["factors"], parent=parent)
        except CandidateRejected as exc:
            if parent is None:
                raise
            path = directory / "parent_prescreen" / (selected["cell_id"] + ".json")
            value = {"target": selected, "parent_blueprint_sha256": canonical_sha256(parent),
                     "rejection_code": exc.stage, "findings": exc.findings, "provider_calls": 0}
            if path.exists() and read_json(path) != value:
                raise ValueError("parent prescreen evidence changed")
            atomic_json(path, value)
            planner.record_outcome(plan, selected["factors"], {"proposal_id": "parent-screen-" + selected["cell_id"],
                "status": "REJECTED", "rejection_code": exc.stage, "evidence_sha256": canonical_sha256(value)})
            continue
        if diversity_target == "family_instance":
            return selected
        control, _ = spec.adapter.compile_pair(proposal, seed=seed)
        evidence = classify(control, index, scenario=spec.scenario_factory())
        if evidence["status"] not in {"EXACT_DUPLICATE", "NEAR_DUPLICATE", "VALID_FAMILY_INSTANCE"}:
            return selected
        path = directory / "history_prescreen" / (selected["cell_id"] + ".json")
        value = {"target": selected, "program_pair_control_sha256": control.content_sha256(),
                 "history_classification": evidence, "provider_calls": 0,
                 "reason": "Existing executable combination; retained as coverage shortfall, not qualified coverage."}
        if path.exists() and read_json(path) != value:
            raise ValueError("history prescreen evidence changed")
        atomic_json(path, value)
        planner.record_outcome(plan, selected["factors"], {"proposal_id": "history-screen-" + selected["cell_id"],
            "status": "REJECTED", "rejection_code": "HISTORICAL_STRUCTURE_ALREADY_SEEN",
            "evidence_sha256": canonical_sha256(value), "diversity": evidence})
    return None


def archive_source(directory: Path):
    manifest = {}
    paths = [path for folder in ("src", "contracts", "config", "scripts/v5")
             for path in (ROOT / folder).rglob("*")
             if path.is_file() and "__pycache__" not in path.parts
             and path.name != ".env" and not path.name.startswith(".env.")]
    paths += [path for path in (ROOT / "pyproject.toml", ROOT / "requirements.txt") if path.is_file()]
    for path in sorted(paths):
        manifest[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    archive_path = directory / "source.zip"
    if not archive_path.exists():
        temporary = directory / "source.zip.tmp"
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(paths):
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("source archive failed CRC verification")
        os.replace(temporary, archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(manifest):
            raise ValueError("source archive is incomplete")
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("source archive differs from its immutable run contract")
    atomic_json(directory / "SOURCE_MANIFEST.json", {"files": manifest, "file_count": len(manifest),
                 "archive_sha256": hashlib.sha256((directory / "source.zip").read_bytes()).hexdigest(),
                 "source_sha256": code_hash(), "runtime_source_sha256": source_tree_hash(ROOT),
                 "command_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "secrets": "Environment and .env excluded; no API request credentials archived"})


def offline(directory: Path, suites: list[str], *, typed: bool = False):
    results = []
    sources = baseline_sources(suites)
    pools = {}
    for suite in suites:
        spec = suite_spec(suite, typed=typed)
        references = baseline_cases(spec, directory.name)
        pools[suite] = [case.as_dict() for case in references]
        for seed in (11, 29):
            if typed:
                blueprint = program_proposal(spec, seed=seed, difficulty="M")
                if suite == "T352" and seed == 29:
                    blueprint["suite_payload"]["report_access"] = "local_receipt_query"
            else:
                blueprint = spec.adapter.default_blueprint(seed=seed)
            compiled = compile_and_gate(spec, blueprint, seed=seed)
            repeat = compile_and_gate(spec, blueprint, seed=seed)
            if compiled["control"].as_dict() != repeat["control"].as_dict() or compiled["risk"].as_dict() != repeat["risk"].as_dict():
                raise AssertionError("same blueprint and seed did not reproduce")
            results.append({"suite": suite, "seed": seed, "passed": compiled["gate"]["passed"],
                            "difficulty": blueprint["difficulty"], "simulation_only": compiled["control"].simulation_only,
                            "pair_sha256": canonical_sha256([compiled["control"].as_dict(), compiled["risk"].as_dict()]),
                            "family_evidence": classify_candidate(compiled["control"], references,
                                                                  scenario=spec.scenario_factory()),
                            "reference_checks": len(compiled["gate"]["runs"])})
    if baseline_sources(suites) != sources:
        raise ValueError("historical reference sources changed during preflight")
    save_baselines(directory, pools, sources)
    report = {"factory_version": FACTORY_VERSION, "source_sha256": code_hash(), "status": "OFFLINE_ENGINEERING_PASS",
              "provider_calls": 0, "checks": results, "quality_scope": "Executable supported-template enrichment only; semantic/model qualification needs live independent audit"}
    report.update(historical_reference_files=len(sources),
                  reference_counts={suite: len(cases) for suite, cases in pools.items()},
                  difficulty_evidence_status="DESIGN_PROXY_ONLY_NOT_EMPIRICALLY_CALIBRATED",
                  new_qualified_global_families=0)
    atomic_json(directory / "PREFLIGHT.json", report)
    return report


async def live(directory: Path, args):
    source_hash = source_tree_hash(ROOT)
    contract_path = directory / "RUN_CONTRACT.json"
    contract = {"source_sha256": source_hash, "factory_version": FACTORY_VERSION, "run_id": args.run_id,
                "suites": args.suite, "typed": args.typed, "trials": args.trials, "seed": args.seed,
                "generator": args.generator, "auditor": args.auditor,
                "command_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    enhanced = getattr(args, "preflight", None) is not None
    routing_profile = getattr(args, "engineering_routing_profile", None)
    if routing_profile and not enhanced:
        raise ValueError("engineering routing does not replace independent auditor preflight/Gold evidence")
    if routing_profile:
        contract["engineering_routing_profile"] = {"path": str(routing_profile.resolve()),
            "sha256": hashlib.sha256(routing_profile.read_bytes()).hexdigest()}
    if enhanced:
        contract.update(preflight=str(args.preflight.resolve()), judge_controls=[str(path.resolve()) for path in args.judge_control],
            acquisition=args.acquisition, staged=args.staged, coverage=args.coverage, auto_typed=args.auto_typed,
            fallback_generator=args.fallback_generator, fallback_auditor=args.fallback_auditor,
            parent=str(args.parent.resolve()) if args.parent else None)
        contract["diversity_target"] = getattr(args, "diversity_target", "new_structure")
        if getattr(args, "history_index", None):
            contract.update(history_index=str(args.history_index.resolve()),
                history_index_sha256=hashlib.sha256(args.history_index.read_bytes()).hexdigest())
    recovery_source = getattr(args, "recover_generation_from", None)
    if recovery_source:
        contract["recover_generation_from"] = recovery_source
    if contract_path.exists() and read_json(contract_path) != contract:
        raise ValueError("run configuration or source changed; use a new run id")
    if not contract_path.exists():
        atomic_json(contract_path, contract)
    if not (directory / "SOURCE_MANIFEST.json").exists():
        archive_source(directory)
    existing = [directory / f"candidate-{index+1:02d}" / "RESULT.json" for index in range(args.trials)]
    if all(path.exists() and read_json(path).get("status") in {"MACHINE_ACCEPTED", "REJECTED", "PROVIDER_FAILED", "REQUEST_UNRESOLVED"} for path in existing):
        if (directory / "BASELINES.json").exists():
            load_baselines(directory, args.suite)
        for path in existing:
            validate_saved_result(path.parent, read_json(path))
        return save_state(directory, [read_json(path) for path in existing], finished=True)
    specs = {suite: suite_spec(suite, typed=args.typed or getattr(args, "auto_typed", False)) for suite in args.suite}
    parent = None
    if enhanced and args.acquisition == "G3":
        parent_result = read_json(args.parent / "RESULT.json")
        validate_saved_result(args.parent, parent_result)
        parent_manifest = read_json(args.parent / "MANIFEST.json")
        if (parent_result.get("status") != "MACHINE_ACCEPTED" or parent_manifest.get("source_sha256") != source_hash
                or any(parent_manifest.get("suite_id") != spec.suite_id
                       or parent_manifest.get("adapter_version") != spec.adapter.adapter_version for spec in specs.values())):
            raise ValueError("G3 requires a bound machine-accepted parent of the same suite, adapter and current source")
        parent = read_json(args.parent / "BLUEPRINT.json")
    baseline_path = directory / "BASELINES.json"
    if not baseline_path.exists():
        sources = baseline_sources(args.suite)
        pools = {suite: [case.as_dict() for case in baseline_cases(spec, args.run_id)]
                 for suite, spec in specs.items()}
        if baseline_sources(args.suite) != sources:
            raise ValueError("historical reference sources changed during baseline preparation")
        save_baselines(directory, pools, sources)
    baselines = {suite: [case_from_dict(raw, allow_dynamic=True) for raw in cases]
                 for suite, cases in load_baselines(directory, args.suite).items()}
    router, historical_index = None, None
    if enhanced:
        from dataclasses import asdict
        from ioabench.v5.ai_generation.history import build_index, discover_sources, verify_sources
        historical_path = directory / "HISTORICAL_INDEX.json"
        if not historical_path.exists():
            historical = read_json(args.history_index) if getattr(args, "history_index", None) else await asyncio.to_thread(
                build_index, ROOT, sources=discover_sources(ROOT))
            verify_sources(ROOT, historical)
            atomic_json(historical_path, historical)
        historical_index = read_json(historical_path)
        verify_sources(ROOT, historical_index)
        gold = {read_json(path / "CONTROL_RESULT.json")["auditor"]: path for path in args.judge_control}
        if routing_profile:
            catalog, generators, endpoint = engineering_contracts(routing_profile, workspace=ROOT,
                model_ids=[args.generator, *args.fallback_generator])
        else:
            catalog, generators, endpoint = qualified_contracts(args.preflight, workspace=ROOT, role="GENERATOR",
                model_ids=[args.generator, *args.fallback_generator])
        _, auditors, audit_endpoint = qualified_contracts(args.preflight, workspace=ROOT, role="INDEPENDENT_AUDITOR",
            model_ids=[args.auditor, *args.fallback_auditor], gold=gold)
        if audit_endpoint != endpoint:
            raise ValueError("auxiliary roles must share the verified endpoint")
        port = AIHubMixAdapter(api_key=_load_api_key(), base_url=endpoint, stop_on_provider_error=True, request_timeout=240)
        router = AuxiliaryRouter(port, [*generators, *auditors], catalog, directory / "auxiliary_calls")
        profiles = {"generator": generators[0].profile, "auditor": auditors[0].profile}
        parameters = {"generator": generators[0].parameters, "auditor": auditors[0].parameters}
        atomic_json(directory / "MODEL_PREPARATION.json", {"catalog": catalog,
            "profiles": {key: asdict(value) for key, value in profiles.items()}, "parameters": parameters,
            "contracts": [asdict(value) for value in [*generators, *auditors]]})
    else:
        port = AIHubMixAdapter(api_key=_load_api_key(), stop_on_provider_error=True, request_timeout=900)
    model_path = directory / "MODEL_PREPARATION.json"
    if model_path.exists():
        from ioabench.models import ModelProfile
        stored = read_json(model_path)
        catalog, profiles, parameters = stored["catalog"], {k: ModelProfile(**v) for k, v in stored["profiles"].items()}, stored["parameters"]
    else:
        try:
            catalog, profiles, parameters = await prepare_models(port, directory, args.generator, args.auditor)
        except Exception as exc:
            event(directory, "MODEL_PREPARATION_FAILED", error_type=type(exc).__name__, error=str(exc))
            state = save_state(directory, [])
            state.update(status="DIAGNOSIS_REQUIRED", failed_stage="MODEL_PREPARATION",
                         error_type=type(exc).__name__, error=str(exc),
                         next_action="Inspect local official AIHubMix documentation, exact model details and saved metadata before a corrected new trial.")
            atomic_json(directory / "RUN_STATE.json", state)
            write_trial_report(directory, state)
            return state
        from dataclasses import asdict
        atomic_json(model_path, {"catalog": list(catalog), "profiles": {k: asdict(v) for k, v in profiles.items()}, "parameters": parameters})
    if (profiles["generator"].model_id != args.generator or profiles["auditor"].model_id != args.auditor
            or profiles["generator"].role != "GENERATOR" or profiles["auditor"].role != "INDEPENDENT_AUDITOR"):
        raise ValueError("cached model roles/identities disagree with immutable run configuration")
    outcomes = []
    planner = CoveragePlanner()
    plans_path = directory / "COVERAGE_PLANS.json"
    plans = read_json(plans_path) if plans_path.exists() else {}
    if enhanced and (args.coverage or args.acquisition == "G3") and not plans:
        from plan_factory_coverage import _constraints, _factors
        for suite, spec in specs.items():
            constraints = _constraints(spec)
            factors = _factors(suite, constraints)
            if suite == "T352":
                factors["reputation_governance"] = ["published_static", "shared_rating_aggregate"]
            def feasible(row):
                try:
                    program_proposal(spec, seed=args.seed, difficulty="M", target=row)
                    return True
                except ValueError:
                    return False
            plans[suite] = planner.plan_factors(factors, feasible=feasible)
        atomic_json(plans_path, plans)
    for index in range(args.trials):
        suite = args.suite[index % len(args.suite)]
        spec = specs[suite]
        difficulty = "M"
        if hasattr(spec.adapter, "default_blueprint") and not (args.typed or getattr(args, "auto_typed", False)):
            difficulty = spec.adapter.default_blueprint(seed=args.seed + index)["difficulty"]
        if recovery_source:
            recover_generation(RUNS / recovery_source, directory / "candidate-01", spec,
                seed=args.seed, difficulty=difficulty, generator=profiles["generator"],
                auditor=profiles["auditor"], parameters=parameters)
        references = list(baselines[suite])
        for prior_index, prior in enumerate(outcomes):
            if prior["status"] == "MACHINE_ACCEPTED" and prior["suite_id"] == spec.suite_id:
                references.append(case_from_dict(read_json(directory / f"candidate-{prior_index+1:02d}" / "PAIR.json")[0], allow_dynamic=True))
        candidate_directory = directory / f"candidate-{index+1:02d}"
        extra = {}
        if enhanced:
            if index:
                pinned = [directory / f"candidate-{prior+1:02d}" / "PAIR.json" for prior in range(index)
                           if (directory / f"candidate-{prior+1:02d}" / "PAIR.json").is_file()]
                historical_index = await asyncio.to_thread(extend_history,
                    read_json(directory / "HISTORICAL_INDEX.json"), pinned)
            target_path = candidate_directory / "ACQUISITION_TARGET.json"
            if target_path.exists():
                selected = read_json(target_path)
            else:
                selected = prescreen_history_targets(spec, plans[suite], historical_index,
                    seed=args.seed + index, directory=directory,
                    diversity_target=getattr(args, "diversity_target", "new_structure"),
                    parent=parent, difficulty=difficulty) if suite in plans else None
                if suite in plans:
                    atomic_json(plans_path, plans)
                    atomic_json(directory / "COVERAGE_REPORT.json", {name: planner.report_coverage(plan) for name, plan in plans.items()})
                    if selected is None:
                        state = save_state(directory, outcomes)
                        state.update(status="COVERAGE_SHORTFALL", stopped_suite=suite,
                            next_action=("No legal selected target changes the qualified parent or meets the declared history scope; retain the finite rejection evidence."
                                if parent is not None else "All selected combinations are already seen or attempted; implement and test a new executable capability before further structural acquisition."))
                        atomic_json(directory / "RUN_STATE.json", state)
                        write_trial_report(directory, state)
                        return state
                atomic_json(target_path, selected)
            target = selected["factors"] if selected else None
            proposal = None
            if args.acquisition in {"G1", "G3"}:
                proposal = program_proposal(spec, seed=args.seed + index, difficulty=difficulty, target=target, parent=parent)
            extra = {"proposal": proposal, "acquisition_strategy": args.acquisition, "router": router,
                     "staged_generation": args.staged, "target": target, "historical_index": historical_index,
                     "parent_directory": args.parent if args.acquisition == "G3" else None}
        result = await run_candidate(candidate_directory, spec,
            seed=args.seed + index, difficulty=difficulty, port=port, catalog=catalog,
            generator=profiles["generator"], auditor=profiles["auditor"], parameters=parameters,
            source_hash=source_hash, references=references, **extra)
        outcomes.append(result)
        if enhanced and selected and suite in plans:
            planner.record_outcome(plans[suite], selected["factors"], {"proposal_id": candidate_directory.name,
                "status": result["status"], "evidence_sha256": canonical_sha256(result),
                "rejection_code": result.get("failed_stage", ""), "diversity": result.get("diversity", {}),
                "difficulty_empirical": "NOT_RUN"})
            atomic_json(plans_path, plans)
            atomic_json(directory / "COVERAGE_REPORT.json", {suite: planner.report_coverage(plan) for suite, plan in plans.items()})
        state = save_state(directory, outcomes)
        if result["status"] in {"PROVIDER_FAILED", "REQUEST_UNRESOLVED", "PIPELINE_FAILED"}:
            state["status"] = "DIAGNOSIS_REQUIRED"
            state["next_action"] = "Preserve evidence, inspect local official AIHubMix docs/model details, or repair versioned local code; never overwrite original judgment."
            atomic_json(directory / "RUN_STATE.json", state)
            return state
    state = save_state(directory, outcomes, finished=True)
    event(directory, "SMALL_TRIALS_COMPLETED", accepted=state["accepted"], new_reference_structures=state["new_reference_structures"])
    return state


def save_state(directory: Path, outcomes, *, finished: bool = False):
    failed = any(row["status"] in {"PROVIDER_FAILED", "REQUEST_UNRESOLVED", "PIPELINE_FAILED"} for row in outcomes)
    state = {"status": "DIAGNOSIS_REQUIRED" if failed else "COMPLETED_SMALL_TRIALS" if finished else "IN_PROGRESS",
             "outcomes": outcomes, "accepted": sum(x["status"] == "MACHINE_ACCEPTED" for x in outcomes),
             "new_reference_structures": sum(bool(x.get("new_family")) for x in outcomes),
             "new_qualified_global_families": 0, "diversity_scope": "Compared against immutable classic 5.1.5/T332 5.1.6 cases, bound dynamic runtime templates and prior accepted trials; structure evidence alone does not establish scientific quality",
             "formal_freeze": False}
    atomic_json(directory / "RUN_STATE.json", state)
    write_trial_report(directory, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--suite", nargs="+", default=["all"])
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--typed", action="store_true", help="use versioned bounded world-variable compilers")
    parser.add_argument("--trials", type=int, default=3, choices=range(1, 19))
    parser.add_argument("--seed", type=int, default=61012)
    parser.add_argument("--generator", default="mimo-v2.6-pro")
    parser.add_argument("--auditor", default="glm-5.3-flash")
    parser.add_argument("--preflight", type=Path, help="bound exact-ID live preflight evidence")
    parser.add_argument("--engineering-routing-profile", type=Path,
                        help="opt-in comparison-bound generator routes; auditor Gold gates still required")
    parser.add_argument("--judge-control", type=Path, nargs="+", default=[])
    parser.add_argument("--fallback-generator", nargs="*", default=[])
    parser.add_argument("--fallback-auditor", nargs="*", default=[])
    parser.add_argument("--auto-typed", action="store_true", help="use each suite's registered bounded compiler")
    parser.add_argument("--acquisition", choices=("G1", "G2", "G3"), default="G2")
    parser.add_argument("--staged", action="store_true", help="four immutable, schema-checked G2 proposal blocks")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--history-index", type=Path, help="hash-bound all-history index, optionally with fixed behavioral probes")
    parser.add_argument("--diversity-target", choices=("new_structure", "family_instance"), default="new_structure",
                        help="new structures prescreen known combinations; instances still pass final full dedup and review")
    parser.add_argument("--parent", type=Path, help="bound accepted candidate directory for G3")
    parser.add_argument("--recover-generation-from", help="prior run/candidate-NN with an unanswered provider-failed audit; one trial only")
    args = parser.parse_args()
    safe_id(args.run_id)
    if args.mode == "live" and (not args.preflight or not args.judge_control):
        parser.error("live acquisition requires actual --preflight and --judge-control evidence")
    if (args.staged and args.acquisition != "G2") or (args.acquisition == "G3" and not args.parent):
        parser.error("staged generation is G2 only; G3 requires --parent")
    if args.mode == "live" and args.coverage and args.acquisition == "G2" and not args.staged:
        parser.error("coverage-targeted AI acquisition requires --staged")
    if args.suite == ["all"]:
        args.suite = list(SUITES)
    if any(suite not in SUITES for suite in args.suite):
        parser.error("suite must be canonical Txxx or all")
    if args.recover_generation_from:
        source_parts = Path(args.recover_generation_from).parts
        if (args.mode != "live" or args.trials != 1 or len(args.suite) != 1
                or len(source_parts) != 2 or source_parts[0] == args.run_id
                or source_parts[1] not in {f"candidate-{index:02d}" for index in range(1, 7)}):
            parser.error("recovery needs one live trial, one suite and another run/candidate-NN")
        safe_id(source_parts[0])
    directory = RUNS / args.run_id
    with _lock(ROOT / "artifacts/v5/overnight_runs/.writer.lock"):
        directory.mkdir(parents=True, exist_ok=True)
        if args.mode == "offline" and (directory / "PREFLIGHT.json").exists():
            raise FileExistsError("preflight evidence is immutable; use new run id")
        report = offline(directory, args.suite, typed=args.typed or args.auto_typed) if args.mode == "offline" else asyncio.run(live(directory, args))
    summary = {key: report[key] for key in ("status", "accepted", "new_reference_structures", "new_qualified_global_families", "provider_calls") if key in report}
    if "checks" in report:
        summary.update(checks=len(report["checks"]), suites=len({row["suite"] for row in report["checks"]}),
                       reference_checks=sum(row["reference_checks"] for row in report["checks"]))
    summary["evidence"] = str(directory)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if report["status"] in {"OFFLINE_ENGINEERING_PASS", "COMPLETED_SMALL_TRIALS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
