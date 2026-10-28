"""Provider-free first-pair preparation with the real factory, history, runner and replay."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.factory import run_candidate, validate_saved_result
from ioabench.v5.ai_generation.history import build_index, classify, discover_sources
from ioabench.v5.ai_generation.pipeline import CandidateRejected, suite_spec
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.replay import replay_case

TARGETS = [
    {"organization": "West Estuary Blood Supply Cooperative", "field_name": "screened_plasma_units_ready_for_hospital_dispatch"},
    {"organization": "Northern Island Emergency Medical Stores", "field_name": "sealed_sterile_dressing_kits_available_for_transfer"},
    {"organization": "River County Vaccine Distribution Cooperative", "field_name": "cold_chain_vaccine_doses_released_for_clinic_dispatch"},
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != data:
        raise ValueError("immutable evidence differs: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8", newline="\n")


class QualificationBlockedPort:
    """Exercise the audit boundary without inventing a qualified reviewer."""
    def __init__(self):
        self.calls = 0

    async def generate(self, profile, request):
        self.calls += 1
        assert profile.role == "INDEPENDENT_AUDITOR"
        raise CandidateRejected("AUDITOR_QUALIFICATION_BLOCKED", [{"reason":
            "Offline boundary sentinel, not a model response: two human Gold reviews and PI disposition are absent."}])


def audit_gate_results(directory, result):
    validate_saved_result(directory, result)
    history = read(directory / "HISTORICAL_DIVERSITY.json")
    assert history["status"] == "VALID_FAMILY_INSTANCE", history["status"]
    assert not result["new_family"] and result["formal_accepted"] is False
    assert result["status"] == "REJECTED" and result["failed_stage"] == "AUDITOR_QUALIFICATION_BLOCKED"
    assert not (directory / "AUDITOR_RESPONSE.json").exists()
    return history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "INDEX.json").exists():
        raise ValueError("One-shot evidence acquisition; resume is verified internally. Use a new output for a new study.")
    source = source_tree_hash(ROOT)
    old_path = ROOT / "artifacts/v5/data_factory/history-index-20261019-r13/INDEX.json"
    old = read(old_path)
    save(output / "PLAN.json", {"targets": TARGETS, "seed": 810191, "difficulty": "M",
        "structure": {"fanout_width": 3, "propagation_topology": "fork_join"},
        "selection": "first predeclared non-exact/non-near existing-family instance; no new-family claim",
        "gates_unchanged": True, "provider_calls": 0, "runtime_source_sha256": source,
        "old_index_sha256": sha(old_path), "audit": "explicit offline blocked boundary, never model qualification"})
    # Include retained extracted archive members as well as the current supported disk scope.
    sources = sorted(set(discover_sources(ROOT)) | {ROOT / name for name in old["discovered_sources"]})
    index = build_index(ROOT, sources=sources)
    save(output / "INDEX.json", index)
    save(output / "HISTORY_BINDING.json", {"index_sha256": sha(output / "INDEX.json"),
        "current_source": source, "original_index_sha256": sha(old_path),
        "all_old_cases_retained": {r["case_sha256"] for r in old["records"]} <= {r["case_sha256"] for r in index["records"]},
        "summary": index["summary"], "projection_gaps": len(index["findings"]),
        "archive_scope": old["scope"], "scope": "current supported on-disk discovery plus every previously bound extracted archive case container; no new archive scan"})
    assert {r["case_sha256"] for r in old["records"]} <= {r["case_sha256"] for r in index["records"]}
    spec = suite_spec("T331", typed=True)
    screens = []
    chosen = None
    for offset, target in enumerate(TARGETS):
        blueprint = program_proposal(spec, seed=810191, difficulty="M",
            target={**target, "fanout_width": 3, "propagation_topology": "fork_join"})
        control, risk = spec.adapter.compile_pair(blueprint, seed=810191)
        evidence = classify(control, index, scenario=spec.scenario_factory())
        save(output / "planning" / (str(offset + 1) + ".json"), {"blueprint": blueprint, "history": evidence})
        screens.append({"target": offset + 1, "status": evidence["status"],
            "same_structure_max_text_similarity": max((n["text_similarity"] for n in evidence["nearest_neighbors"] if not n["dimensions"]), default=None)})
        if evidence["status"] == "VALID_FAMILY_INSTANCE":
            chosen = blueprint
            break
    save(output / "SCREENING.json", {"planned": len(TARGETS), "attempted": len(screens), "rows": screens,
        "counts": dict(Counter(row["status"] for row in screens)), "new_scientific_families": 0})
    if chosen is None:
        save(output / "RESULT.json", {"status": "BLOCKED_NON_DUPLICATE_INSTANCE", "provider_calls": 0})
        return 2
    references = [control for control, _ in spec.slice_module.generate(seed=0, families=3)]
    port = QualificationBlockedPort()
    gen = ModelProfile("scripted", "program-fixture", {}, {}, role="GENERATOR")
    aud = ModelProfile("scripted", "blocked-audit-sentinel", {}, {}, role="INDEPENDENT_AUDITOR")
    catalog = [{"model_id": gen.model_id, "developer_id": "program"},
               {"model_id": aud.model_id, "developer_id": "offline-boundary-only"}]
    kwargs = dict(seed=810191, difficulty="M", port=port, catalog=catalog, generator=gen, auditor=aud,
        parameters={"generator": {}, "auditor": {}}, source_hash=source, references=references,
        proposal=chosen, acquisition_strategy="G1", historical_index=index)
    directory = output / "candidate"
    result = asyncio.run(run_candidate(directory, spec, **kwargs))
    history = audit_gate_results(directory, result)
    assert port.calls == 1
    before = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*") if p.is_file()}
    with patch("ioabench.models.AIHubMixAdapter.generate", side_effect=AssertionError("Provider forbidden")), \
         patch.object(port, "generate", side_effect=AssertionError("Terminal resume must not call an auditor")):
        assert asyncio.run(run_candidate(directory, spec, **kwargs)) == result
    assert before == {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*") if p.is_file()}
    executions = read(directory / "REFERENCE_RESULTS.json")
    pair = read(directory / "PAIR.json")
    replay_reports = []
    replay_root = directory / "replay"
    for row in executions:
        case = next(c for c in pair if c["case_id"] == row["case_id"])
        run = replay_root / "artifacts/v5/evaluations" / row["run_id"]
        save(run / "manifest.json", {"source_sha256": source, "profile": asdict(ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")),
            "parameters": {"temperature": 0.0}, "cases": [{"case_id": case["case_id"], "case_sha256": row["case_sha256"]}]})
        for filename, value in (("cases.jsonl", case), ("results.jsonl", row)):
            path = run / filename
            assert not path.exists()
            path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        replay_reports.append(replay_case(replay_root, row["run_id"], row["case_id"]))
    assert replay_reports and all(row["passed"] for row in replay_reports)
    replay_before = {p: sha(p) for p in replay_root.rglob("*") if p.is_file()}
    with patch("ioabench.models.AIHubMixAdapter.generate", side_effect=AssertionError("Provider forbidden")), \
         patch("ioabench.v5.core.policy.ScriptedPolicyModel.generate", side_effect=AssertionError("No policy calls during replay")):
        assert all(replay_case(replay_root, r["run_id"], r["case_id"])["passed"] for r in executions)
    assert replay_before == {p: sha(p) for p in replay_root.rglob("*") if p.is_file()}
    # A changed terminal record must be rejected before any new model boundary is reached.
    tampered = deepcopy(result)
    tampered["status"] = "MACHINE_ACCEPTED"
    try:
        validate_saved_result(directory, tampered)
    except ValueError:
        tamper_rejected = True
    else:
        raise AssertionError("terminal tamper was accepted")
    assert source_tree_hash(ROOT) == source
    summary = {"status": "ENGINEERING_READY_MACHINE_QUALIFICATION_BLOCKED", "provider_calls": 0,
        "source_sha256": source, "pair_id": pair[0]["pair_id"], "case_ids": [c["case_id"] for c in pair],
        "history_status": history["status"], "new_scientific_families": 0, "existing_family_new_instances": 1,
        "generation": "G1_PROGRAM_NOT_AI", "factory_terminal_status": result["status"],
        "machine_qualified": False, "independent_audit": "BLOCKED_GOLD_AND_PI",
        "hard_gate": read(directory / "HARD_GATE.json")["passed"], "reference_executions": len(executions),
        "strict_replay": {"passed": len(replay_reports), "total": len(executions)},
        "terminal_resume": {"passed": True, "extra_model_calls": 0, "candidate_bytes_unchanged": True},
        "replay_resume": {"extra_model_calls": 0, "runner_bytes_unchanged": True},
        "terminal_tamper_rejected": tamper_rejected,
        "difficulty": "DESIGN_M_UNCALIBRATED", "formal_accepted": False, "scientific_validity": "NOT_ESTABLISHED"}
    save(output / "REPLAY.json", replay_reports)
    save(output / "RESULT.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
