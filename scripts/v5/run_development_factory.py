"""Opt-in official G2 -> hard gates -> isolated audits -> development pool; no formal promotion."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]

from ioabench.config.loader import load_workspace_env
from ioabench.models import DeepSeekAdapter
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.development import (
    VERSION, admission, baseline_census, read, sha, structure_vector, validate_policy,
)
from ioabench.v5.ai_generation.direct_deepseek import (
    DirectStudy, candidate_result, generate_candidate, immutable, strict_checks,
)
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.ai_generation.quality import dedup_features
from ioabench.hashing import canonical_sha256
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.evaluation import atomic_json, writer_lock
from run_deepseek_g2 import snapshot, prepare_history

PREVIOUS = ROOT / "artifacts/v5/data_factory/direct_deepseek_g2/deepseek-g2-20261020T0430Z"
DEFAULT_OUT = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020"


def policy_for(out):
    policy = validate_policy(yaml.safe_load((ROOT / "config/v5/deepseek_development_policy_v1.yaml").read_text(encoding="utf-8")))
    immutable(out / "DEVELOPMENT_POLICY.json", policy)
    return policy


def baseline(out):
    policy_for(out)
    census = baseline_census(PREVIOUS, out)
    prior = read(PREVIOUS / "PROTECTED_BASELINE.json")
    extra = {path.relative_to(ROOT).as_posix(): sha(path) for path in PREVIOUS.rglob("*")
        if path.is_file() and not path.name.endswith(".lock") and "__pycache__" not in path.parts}
    immutable(out / "PROTECTED_BASELINE.json", {"previous_inventory": str(PREVIOUS / "PROTECTED_BASELINE.json"),
        "previous_inventory_sha256": sha(PREVIOUS / "PROTECTED_BASELINE.json"), "files": {**prior["files"], **extra}})
    load_workspace_env(ROOT / ".env")
    if not (out / "ENVIRONMENT.json").exists():
        immutable(out / "ENVIRONMENT.json", {"at_utc": datetime.now(timezone.utc).isoformat(),
        "secret_env": "DEEPSEEK_API_KEY", "configured": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "baseline_git": "e6e3ecff0ce3661251b8efb2cea20ca73301f185", "new_goal": False,
        "prior_regression": "1652 PASS in retained FULL_REGRESSION_R2.xml", "prior_delivery": read(
            ROOT / "exports/deepseek-g2-handoff-20261020/FINAL_DELIVERY_VERIFICATION.json")})
    return {"pair_count": census["pair_count"], "protected_files": len(prior["files"]) + len(extra), "provider_calls": 0}


async def study_for(out):
    load_workspace_env(ROOT / ".env")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("DEEPSEEK_API_KEY missing; no value logged")
    port = DeepSeekAdapter(request_timeout=900)
    catalog_path = out / "MODEL_CATALOG.json"
    if catalog_path.exists():
        catalog = read(catalog_path)
    else:
        catalog = list(await port.discover_models())
        immutable(catalog_path, catalog)
    return DirectStudy(out, port, catalog)


def supplemental_checks(source, destination):
    """T332 has two policies: retain four old checks and record a second real four-check batch."""
    if len(read(source / "REPLAY.json")) >= 6:
        return []
    if (destination / "REPLAY.json").exists():
        return read(destination / "REPLAY.json")
    source_row = candidate_result(source)
    task = source_row["task"]
    spec = suite_spec(task["suite"], typed=True)
    compiled = compile_and_gate(spec, read(source / "BLUEPRINT.json"), seed=task["seed"])
    if [compiled[arm].as_dict() for arm in ("control", "risk")] != read(source / "PAIR.json"):
        raise ValueError("supplemental reference compile changed the retained pair")
    destination.mkdir(parents=True, exist_ok=True)
    count = strict_checks(destination, spec, compiled)
    immutable(destination / "SUPPLEMENTAL_BINDING.json", {"source_pair_sha256": sha(source / "PAIR.json"),
        "source_runtime_sha256": source_tree_hash(ROOT), "recorded_checks": count,
        "configured_policies": list(spec.policies), "distinct_policy_count": len(spec.policies),
        "reason": "additional batch of the two existing policies; no invented recovery policy",
        "evidence_sha256": {path.relative_to(destination).as_posix(): sha(path) for path in destination.rglob("*")
            if path.is_file() and path.name != "SUPPLEMENTAL_BINDING.json" and not path.name.endswith(".lock")}})
    return read(destination / "REPLAY.json")


async def audit_one(study, source, destination, *, history_scope="FULL_HISTORY", execution_binding=None):
    from ioabench.v5.ai_generation.development_audit import audit_pair, CURRENT_PROTOCOL
    final = destination / "ADMISSION.json"
    if final.exists():
        # Revalidate the sealed source and isolated review without a provider call.
        candidate_result(source)
    if execution_binding is not None and not (destination / "EXECUTION_BINDING.json").exists():
        immutable(destination / "EXECUTION_BINDING.json", execution_binding)
    audit_directory = destination / "audit"
    audit_profile = yaml.safe_load((ROOT / "config/v5/deepseek_development_audit_v1_1.yaml").read_text(encoding="utf-8"))
    if (audit_profile["version"] != CURRENT_PROTOCOL or audit_profile["max_tokens"] != 65536
            or audit_profile["efforts"] != ["high", "max"] or audit_profile["formal_scientific_claims"] is not False):
        raise ValueError("unexpected development review profile")
    settings = audit_directory / "AUDIT_SETTINGS.json"
    cap = read(settings)["max_tokens"] if settings.exists() else 16384 if (audit_directory / "AUDIT_RESULT.json").exists() else audit_profile["max_tokens"]
    packet_path = audit_directory / "AUDIT_PACKET.json"
    protocol = read(packet_path)["version"] if packet_path.exists() else CURRENT_PROTOCOL
    review = await audit_pair(study, source, audit_directory, max_tokens=cap, protocol=protocol)
    pair = read(source / "PAIR.json")
    control = next(case_from_dict(case, allow_dynamic=True) for case in pair if case["arm"] == "CONTROL")
    vector = structure_vector(control)
    supplementary = await asyncio.to_thread(supplemental_checks, source, destination / "supplemental")
    result = admission(source, review, vector, audit_directory=destination / "audit", history_scope=history_scope,
        supplemental_directory=destination / "supplemental" if supplementary else None)
    result.update(source_directory=source.relative_to(ROOT).as_posix(),
        pair_sha256=sha(source / "PAIR.json"), suite=control.suite_id[:4], id=source.name)
    immutable(final, result)
    return result


def extend_history(index, source):
    if not (source / "PAIR.json").exists():
        return
    for name in ("PAIR.json", "RESULT.json"):
        index["source_sha256"][(source / name).relative_to(ROOT).as_posix()] = sha(source / name)
    probes = read(source / "BEHAVIORAL_PROBES.json")["by_case_sha256"] if (source / "BEHAVIORAL_PROBES.json").exists() else {}
    existing = {row["case_sha256"] for row in index["records"]}
    for raw in read(source / "PAIR.json"):
        case = case_from_dict(raw, allow_dynamic=True)
        digest = case.content_sha256()
        if digest in existing:
            continue
        spec = suite_spec(case.suite_id, typed=True)
        index["records"].append({"case_sha256": digest,
            "features": dedup_features(case, scenario=spec.scenario_factory()),
            "behavioral_probe_signature": probes.get(digest), "occurrences": [{
                "source": (source / "PAIR.json").relative_to(ROOT).as_posix(), "status": read(source / "RESULT.json")["status"],
                "scientific_qualification": "NOT_ESTABLISHED_BY_INDEX"}]})


async def run(out, phase, plan=None, limit=None):
    policy = policy_for(out)
    if phase == "baseline":
        return baseline(out)
    if phase == "verify-history":
        baseline_value = read(out / "PROTECTED_BASELINE.json")
        changes = [name for name, digest in baseline_value["files"].items()
            if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
        value = {"status": "FAIL" if changes else "PASS", "file_count": len(baseline_value["files"]), "changes": changes, "provider_calls": 0}
        atomic_json(out / "PROTECTED_VERIFICATION.json", value)
        if changes:
            raise ValueError("protected historical files changed")
        return value
    runtime = snapshot(out)
    execution_binding = {"runtime_sha256": runtime, "script_sha256": sha(Path(__file__)), "phase": phase}
    immutable(out / (phase.upper() + "_SOURCE_BINDING-" + runtime[:12] + "-" + sha(Path(__file__))[:8] + ".json"), execution_binding)
    immutable(out / "execution_scripts" / (sha(Path(__file__)) + ".json"), {"sha256": sha(Path(__file__)), "path": "scripts/v5/run_development_factory.py"})
    script_copy = out / "execution_scripts" / (sha(Path(__file__)) + ".py")
    if not script_copy.exists():
        script_copy.write_bytes(Path(__file__).read_bytes())
    if phase == "prepare":
        return prepare_history(out)["summary"]
    if phase == "resume":
        class ClosedStudy:
            def __init__(self):
                self.out = out
            async def invoke(self, *args, **kwargs):
                raise AssertionError("terminal resume attempted a model call")
        results = []
        before = sha(out / "REQUEST_LEDGER.jsonl") if (out / "REQUEST_LEDGER.jsonl").exists() else None
        for path in sorted((out / "reviews").glob("*/ADMISSION.json")):
            value = read(path)
            result = await audit_one(ClosedStudy(), ROOT / value["source_directory"], path.parent,
                history_scope=value["history_scope"])
            assert result == value
            results.append(result)
        assert before == (sha(out / "REQUEST_LEDGER.jsonl") if (out / "REQUEST_LEDGER.jsonl").exists() else None)
        value = {"status": "PASS", "terminal_admissions": len(results), "provider_calls": 0, "ledger_unchanged": True}
        atomic_json(out / "CLI_NO_RESEND.json", value)
        return value
    study = await study_for(out)
    if phase == "audit":
        census = read(out / "BASELINE_CENSUS.json")
        selected = census["pairs"]
        if plan:
            requested = read(plan)
            immutable(out / "plans" / plan.name, requested)
            selected = [row for row in selected if row["id"] in requested["ids"]]
        results, started = [], 0
        for row in selected:
            destination = out / "reviews" / row["id"]
            if limit is not None and started >= limit and not (destination / "ADMISSION.json").exists():
                break
            if study.stop.exists():
                break
            existed = (destination / "ADMISSION.json").exists()
            result = await audit_one(study, Path(row["source_directory"]), destination, execution_binding=execution_binding)
            started += not existed
            results.append(result)
            print(row["id"], result["status"], flush=True)
        return dict(Counter(row["status"] for row in results))
    if phase == "generate":
        if plan is None:
            raise ValueError("frozen versioned plan required")
        value = read(plan)
        immutable(out / "plans" / plan.name, value)
        index = prepare_history(out)
        for seal in sorted((out / "candidates").glob("*/TERMINAL.json")):
            candidate_result(seal.parent)
        for retained in sorted((out / "candidates").glob("*/RESULT.json")):
            extend_history(index, retained.parent)
        base_references = [row["features"] for row in index["records"]]
        rows, started = [], 0
        for task in value["tasks"]:
            directory = out / "candidates" / task["id"]
            if limit is not None and started >= limit and not (directory / "RESULT.json").exists():
                break
            if study.stop.exists():
                break
            selected_index, references, history_scope = index, base_references, "FULL_HISTORY"
            if task["suite"] == "T322":
                from ioabench.v5.ai_generation.t322_history import version_scoped_index
                immutable(out / "history" / ("overlay-" + canonical_sha256(index) + ".json"), index)
                selected_index, scope_report = version_scoped_index(index)
                immutable(out / ("T322_VERSION_SCOPE-" + scope_report["full_history_index_sha256"] + ".json"), scope_report)
                references = [row["features"] for row in selected_index["records"]]
                history_scope = "VERSION_SCOPED"
            immutable(out / "history" / ("overlay-" + canonical_sha256(selected_index) + ".json"), selected_index)
            existed = (directory / "RESULT.json").exists()
            result = candidate_result(directory) if existed else await generate_candidate(
                study, task, selected_index, references, workspace=ROOT, development_policy=policy)
            started += not existed
            if result["status"] == "PASS":
                result = await audit_one(study, directory, out / "reviews" / task["id"], history_scope=history_scope,
                    execution_binding=execution_binding)
            extend_history(index, directory)
            base_references = [row["features"] for row in index["records"]]
            rows.append(result)
            print(task["id"], result["status"], result.get("failed_stage", ""), flush=True)
            if source_tree_hash(ROOT) != runtime:
                raise ValueError("source changed during the frozen generation batch")
        return dict(Counter(row["status"] for row in rows))
    if phase == "calibrate":
        from calibrate_development_audit import run_calibration
        return await run_calibration(study, out)
    raise ValueError("unknown phase")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--phase", required=True, choices=("baseline", "prepare", "audit", "calibrate", "generate", "resume", "verify-history"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--original-root", type=Path, help="read-only mapping for an extracted sealed handoff")
    args = parser.parse_args()
    out = args.out.resolve()
    if args.original_root:
        if args.phase != "resume":
            raise ValueError("original-root mapping is only allowed for zero-call resume")
        os.environ["IOABENCH_EVIDENCE_ORIGINAL_ROOT"] = str(args.original_root.resolve())
    if not out.is_relative_to(ROOT / "artifacts/v5/data_factory/dev_auto_audit"):
        raise ValueError("development evidence requires its isolated root")
    with writer_lock(ROOT / "artifacts/v5/data_factory"), writer_lock(out):
        result = asyncio.run(run(out, args.phase, args.plan, args.limit))
    print(json.dumps({"phase": args.phase, "result": result}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
