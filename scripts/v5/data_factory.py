"""Shared data-factory preflight and bounded experimental trials. No bulk production/freeze."""
from __future__ import annotations

import argparse
import asyncio
import json
import hashlib
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.factory import FACTORY_VERSION, prepare_models, run_candidate, recover_generation, read_json, event, validate_saved_result, write_trial_report
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.ai_generation.quality import classify_candidate
from ioabench.v5.core.case import SUITES, case_from_dict
from ioabench.v5.evaluation import atomic_json, read_cases, safe_id
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
                 "source_sha256": code_hash(), "secrets": "Environment and .env excluded; no API request credentials archived"})


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
                subtype = {"T312": "T312-S2", "T331": "T331-S5", "T352": "T352-S1"}[suite]
                blueprint = spec.adapter.generator_constraints(subtype=subtype, difficulty="M")["example_blueprint"]
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
    source_hash = code_hash()
    contract_path = directory / "RUN_CONTRACT.json"
    contract = {"source_sha256": source_hash, "factory_version": FACTORY_VERSION, "run_id": args.run_id,
                "suites": args.suite, "typed": args.typed, "trials": args.trials, "seed": args.seed,
                "generator": args.generator, "auditor": args.auditor}
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
    specs = {suite: suite_spec(suite, typed=args.typed) for suite in args.suite}
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
    for index in range(args.trials):
        suite = args.suite[index % len(args.suite)]
        spec = specs[suite]
        difficulty = "M"
        if not args.typed:
            difficulty = spec.adapter.default_blueprint(seed=args.seed + index)["difficulty"]
        if recovery_source:
            recover_generation(RUNS / recovery_source, directory / "candidate-01", spec,
                seed=args.seed, difficulty=difficulty, generator=profiles["generator"],
                auditor=profiles["auditor"], parameters=parameters)
        references = list(baselines[suite])
        for prior_index, prior in enumerate(outcomes):
            if prior["status"] == "MACHINE_ACCEPTED" and prior["suite_id"] == spec.suite_id:
                references.append(case_from_dict(read_json(directory / f"candidate-{prior_index+1:02d}" / "PAIR.json")[0], allow_dynamic=True))
        result = await run_candidate(directory / f"candidate-{index+1:02d}", spec,
            seed=args.seed + index, difficulty=difficulty, port=port, catalog=catalog,
            generator=profiles["generator"], auditor=profiles["auditor"], parameters=parameters,
            source_hash=source_hash, references=references)
        outcomes.append(result)
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
    parser.add_argument("--typed", action="store_true", help="use supported world-variable compilers (T312/T331/T352)")
    parser.add_argument("--trials", type=int, default=3, choices=range(1, 7))
    parser.add_argument("--seed", type=int, default=61012)
    parser.add_argument("--generator", default="claude-sonnet-5-5")
    parser.add_argument("--auditor", default="gpt-6-astra")
    parser.add_argument("--recover-generation-from", help="prior run/candidate-NN with an unanswered provider-failed audit; one trial only")
    args = parser.parse_args()
    safe_id(args.run_id)
    if args.suite == ["all"]:
        args.suite = list(SUITES)
    if any(suite not in SUITES for suite in args.suite):
        parser.error("suite must be canonical Txxx or all")
    if args.typed and any(suite not in {"T312", "T331", "T352"} for suite in args.suite):
        parser.error("typed mode supports only T312/T331/T352; enrichment supports all18")
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
        report = offline(directory, args.suite, typed=args.typed) if args.mode == "offline" else asyncio.run(live(directory, args))
    summary = {key: report[key] for key in ("status", "accepted", "new_reference_structures", "new_qualified_global_families", "provider_calls") if key in report}
    if "checks" in report:
        summary.update(checks=len(report["checks"]), suites=len({row["suite"] for row in report["checks"]}),
                       reference_checks=sum(row["reference_checks"] for row in report["checks"]))
    summary["evidence"] = str(directory)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if report["status"] in {"OFFLINE_ENGINEERING_PASS", "COMPLETED_SMALL_TRIALS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
