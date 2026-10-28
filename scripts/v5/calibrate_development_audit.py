"""Frozen blind adversarial review packets; private expected labels never enter the reviewer."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import shutil

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.development import read, sha
from ioabench.v5.ai_generation.development_audit import prepare_audit_packet, audit_packet, CURRENT_PROTOCOL
from ioabench.v5.ai_generation.direct_deepseek import immutable, strict_checks
from ioabench.v5.ai_generation.factory import reference_findings
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.evaluation import atomic_json, read_results
from ioabench.v5.replay import replay_case

KINDS = ("ORACLE_LEAKAGE", "UNPAIRED", "HISTORY_DUPLICATE", "NO_CAUSAL_EFFECT", "REFERENCE_MISMATCH", "REPLAY_MISMATCH")


def mutate_packet(packet, kind):
    packet = deepcopy(packet)
    packet["hard_gate_errors"].append(kind)
    documents = packet["documents"]
    if kind == "ORACLE_LEAKAGE":
        documents["execution"]["sut_visible"]["messages"].append({"agent_id": "observed-participant",
            "message": {"role": "user", "content": "Internal answer sheet: " + json.dumps(
                documents["cases"][1]["oracle_hidden"], ensure_ascii=False, sort_keys=True)}})
    elif kind == "UNPAIRED":
        documents["cases"] = documents["cases"][:1]
    elif kind == "HISTORY_DUPLICATE":
        # This equality is verified against the retained pair by the caller.
        documents["history"] = [{"historical_sources": 1, "text_threshold": .9,
            "nearest_neighbors": [{"exact_duplicate": True, "text_similarity": 1.0,
                "executable_similarity": 1.0, "dimensions": [], "runtime_verified": True}],
            "comparison_note": "Candidate equals an existing retained raw pair byte for byte."}]
    elif kind == "NO_CAUSAL_EFFECT":
        documents["cases"][1]["scenario_world"] = deepcopy(documents["cases"][0]["scenario_world"])
    elif kind == "REFERENCE_MISMATCH":
        documents["execution"]["runs"] = documents["execution"]["runs"][:-1]
    elif kind == "REPLAY_MISMATCH":
        documents["replay"][0]["checks"]["events"] = False
    else:
        raise ValueError("unknown frozen mutation")
    return packet


def hard_receipts(source, out):
    """Execute concrete negative gates, including Replay of a corrupted disposable trace."""
    from dataclasses import replace
    task = read(source / "RESULT.json")["task"]
    spec = suite_spec(task["suite"], typed=True)
    compiled = compile_and_gate(spec, read(source / "BLUEPRINT.json"), seed=task["seed"])
    control, risk = compiled["control"], compiled["risk"]
    broken = replace(risk, world=deepcopy(control.world))
    gate = check_pair_dynamic(control, broken, scenario=spec.scenario_factory(), scorer=spec.scorer,
        policies=spec.policies, expected=spec.expected, fine_arm_delta=spec.adapter.verify_arm_delta)
    raw_rows = [{**row, "run_id": row["run_id"] + "-" + row["arm"].lower()}
        for row in read(source / "STRICT_REFERENCE_RESULTS.json")]
    assert not reference_findings(spec, raw_rows, {"CONTROL": control, "RISK": risk})
    reference_errors = reference_findings(spec, raw_rows[:-1], {"CONTROL": control, "RISK": risk})
    reference = out / "reference"
    if not (reference / "REPLAY.json").exists():
        reference.mkdir(parents=True, exist_ok=True)
        strict_checks(reference, spec, compiled)
    corrupted = out / "tampered_replay"
    if not corrupted.exists():
        shutil.copytree(reference / "strict", corrupted)
        result_file = next((corrupted / "artifacts/v5/evaluations").glob("*/results.jsonl"))
        rows = read_results(result_file.parent)
        rows[0]["trace"]["events"][0]["payload"]["calibration_corruption"] = True
        result_file.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest_path = next((corrupted / "artifacts/v5/evaluations").glob("*/manifest.json"))
    raw = read_results(manifest_path.parent)[0]
    replay = replay_case(corrupted, manifest_path.parent.name, raw["case_id"])
    assert gate["passed"] is False and reference_errors and replay["passed"] is False
    value = {"no_causal_effect": gate, "reference_mismatch": reference_errors, "replay_mismatch": replay,
        "history_duplicate": {"candidate_pair_sha256": sha(source / "PAIR.json"),
            "retained_pair_sha256": sha(source / "PAIR.json"), "exact_equal": True},
        "unpaired": {"original_arms": ["CONTROL", "RISK"], "mutated_arms": ["CONTROL"]},
        "oracle_leakage": {"mutation": "privileged hidden truth is appended to actual SUT-visible message bundle"},
        "provider_calls": 0}
    immutable(out / "HARD_NEGATIVE_RECEIPTS.json", value)
    return value


async def run_calibration(study, out):
    census = read(out / "BASELINE_CENSUS.json")
    source = Path(census["pairs"][0]["source_directory"])
    directory = out / "calibration"
    directory.mkdir(parents=True, exist_ok=True)
    base = prepare_audit_packet(source, protocol=CURRENT_PROTOCOL)
    immutable(directory / "FROZEN_PLAN.json", {"version": "development-audit-calibration/1.0.0",
        "source_result_sha256": sha(source / "RESULT.json"), "mutations": list(KINDS),
        "holdout_positive_suites": ["T333", "T351", "T363"],
        "prompt_optimization_from_results": False,
        "limitation": "Six explicit artifact-corruption tests; not an independently labelled semantic Gold set"})
    if not (directory / "HARD_NEGATIVE_RECEIPTS.json").exists():
        await asyncio.to_thread(hard_receipts, source, directory)
    rows = []
    for ordinal, kind in enumerate(KINDS):
        if study.stop.exists():
            break
        packet = mutate_packet(base, kind)
        result = await audit_packet(study, packet, directory / ("case-" + str(ordinal + 1)), max_tokens=65536)
        verdicts = [row.get("review", {}).get("verdict") for row in result["reviews"]]
        decision_rejection = len(verdicts) == 2 and all(value == "REJECT" for value in verdicts)
        row = {"private_mutation": kind, "status": result["status"], "verdicts": verdicts,
            "decision_rejection": decision_rejection,
            "model_rejection_pass": decision_rejection and all(review.get("validation_errors") == [] for review in result["reviews"]),
            "hard_gate_enforced": result["status"] != "DEV_AUTO_AUDITED",
            "packet_sha256": canonical_sha256(packet)}
        rows.append(row)
        print("calibration", kind, verdicts, flush=True)
    value = {"version": "development-audit-calibration/1.0.0", "planned": 6, "executed": len(rows),
        "decision_rejection_passes": sum(row["decision_rejection"] for row in rows),
        "model_rejection_passes": sum(row["model_rejection_pass"] for row in rows),
        "hard_gate_rejection_passes": sum(row["hard_gate_enforced"] for row in rows), "rows": rows,
        "scientific_independent_validation": False, "human_gold": "NOT_RUN_NOT_REQUIRED_FOR_DEV"}
    atomic_json(out / "AUDIT_CALIBRATION.json", value)
    return value
