"""Versioned development admission around the existing G2 engine; no scientific promotion."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json

from ioabench.hashing import canonical_sha256
from ioabench.models.aihubmix import DEFAULT_BASE_URL
from .direct_deepseek import candidate_result, immutable
from .pipeline import suite_spec
from .quality import dedup_features
from ioabench.v5.core.case import case_from_dict

VERSION = "ioabench.v5.development-factory/1.0.0"
VECTOR_VERSION = "ioabench.v5.development-structure/1.0.0"
POLICY_V1_1 = "ioabench.v5.development-policy/1.1.0"
POLICY_V1_2 = "ioabench.v5.development-policy/1.2.0"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _expected_policy(version):
    if version in {POLICY_V1_1, POLICY_V1_2}:
        # Keep frozen overseas policies valid; the mainland route has its own version.
        return {"version": version, "scope": "DEVELOPMENT_AUTO_AUDITED",
                "provider": "aihubmix", "base_url": "https://aihubmix.com/v1" if version == POLICY_V1_1 else DEFAULT_BASE_URL,
                "model_id": "deepseek-v4.1-flash-1017",
                "cross_family_exclusion": False, "human_gold_prerequisite": False,
                "formal_scientific_claims": False, "same_model_audit_independent_science": False,
                "formal_accepted": False, "minimum_recorded_strict_replays": 6,
                "near_duplicate_threshold": .9, "audit_efforts": ["high", "max"]}
    return {"version": "ioabench.v5.development-policy/1.0.0", "scope": "DEVELOPMENT_AUTO_AUDITED",
        "provider": "deepseek", "base_url": "https://api.deepseek.com", "model_id": "deepseek-flash",
        "cross_family_exclusion": False, "human_gold_prerequisite": False,
        "formal_scientific_claims": False, "same_model_audit_independent_science": False,
        "formal_accepted": False, "minimum_recorded_strict_replays": 6,
        "near_duplicate_threshold": .9, "audit_efforts": ["high", "max"]}


def validate_policy(policy):
    expected = _expected_policy(policy.get("version"))
    if any(policy.get(key) != value for key, value in expected.items()):
        raise ValueError("invalid opt-in development policy; formal gates cannot be disabled here")
    return policy


def structure_vector(case):
    """Count only runtime-consumed factors, never text, seeds or keyed initial-state IDs."""
    spec = suite_spec(case.suite_id, typed=True)
    features = dedup_features(case, scenario=spec.scenario_factory())
    structure = features["structure"]
    consumed = {key: structure[key] for key in ("agents", "tools", "topology", "event_schedule",
        "executable_factors", "evidence_access") if key in structure}
    return {"version": VECTOR_VERSION, "suite": case.suite_id.split("-")[0],
        "runtime_consumed": consumed, "structural_cell_sha256": canonical_sha256(consumed),
        "excluded_from_novelty": ["case_id", "seed", "domain", "narrative", "initial_state_mapping_keys"],
        "unimplemented_dimensions": ["arbitrary topology", "empirical difficulty", "new scientific family"],
        "difficulty": {"design_intent": case.difficulty, "calibrated": False},
        "simulation_only": case.suite_id[:4] in {"T361", "T362", "T363"}}


def baseline_census(previous, out):
    previous, out = Path(previous), Path(out)
    plan = read(previous / "POOL_PLAN_V5.json")
    rows, seen = [], set()
    for task in plan["tasks"]:
        directory = previous / "candidates" / task["id"]
        if not (directory / "RESULT.json").exists() or directory in seen:
            continue
        seen.add(directory)
        result = candidate_result(directory)
        if result["status"] != "PASS":
            continue
        pair = [case_from_dict(value, allow_dynamic=True) for value in read(directory / "PAIR.json")]
        if {case.arm for case in pair} != {"CONTROL", "RISK"}:
            raise ValueError("baseline pair is incomplete")
        control = next(case for case in pair if case.arm == "CONTROL")
        replay = read(directory / "REPLAY.json")
        if not replay or not all(item.get("passed") is True for item in replay):
            raise ValueError("baseline replay failure")
        rows.append({"id": task["id"], "source_directory": directory.as_posix(),
            "source_result_sha256": sha(directory / "RESULT.json"), "pair_sha256": sha(directory / "PAIR.json"),
            "source_runtime_sha256": read(directory / "MANIFEST.json")["source_sha256"],
            "suite": control.suite_id[:4], "reference_replay_rows": len(replay),
            "history_basis": "original sealed all-history check at generation, not a new novelty claim",
            "vector": structure_vector(control), "source_evidence_sha256": result["evidence_sha256"]})
    if len(rows) != 32:
        raise ValueError("baseline must contain exactly the retained 32 pairs")
    value = {"version": VERSION, "provider_calls": 0, "pairs": rows, "pair_count": len(rows),
        "suites": dict(sorted(Counter(row["suite"] for row in rows).items())), "new_scientific_families": 0,
        "generation_requests": 0, "baseline_replay_rows": sum(row["reference_replay_rows"] for row in rows)}
    immutable(out / "BASELINE_CENSUS.json", value)
    return value


def admission(source, audit, vector, *, audit_directory, history_scope="FULL_HISTORY", supplemental_directory=None):
    """AI agreement cannot override execution, provenance, history or Replay gates."""
    errors = []
    source = Path(source)
    result = candidate_result(source)
    from .development_audit import _saved_result, evidence_path, prepare_audit_packet
    packet = read(Path(audit_directory) / "AUDIT_PACKET.json")
    if evidence_path(packet["source_binding"]["directory"]) != source.resolve():
        raise ValueError("audit terminal evidence changed: different source directory")
    verified = _saved_result(Path(audit_directory), packet)
    if verified != audit:
        raise ValueError("audit belongs to a different source or terminal")
    projected = prepare_audit_packet(source, protocol=packet["version"])
    # Early 1.1 packets predate the additive trace check; their source bytes and
    # semantic documents remain frozen, with the separate forensic receipt retained.
    if "tool_observation_consistency" not in packet["documents"]["execution"]:
        projected["documents"]["execution"].pop("tool_observation_consistency", None)
    if (projected["documents"] != packet["documents"]
            or not set(projected["hard_gate_errors"]) <= set(packet["hard_gate_errors"])):
        raise ValueError("audit documents differ from the sealed source facts or omit hard failures")
    if "MANIFEST.json" not in result["evidence_sha256"]:
        raise ValueError("history scope requires a sealed source manifest")
    scopes = [history_scope, *(record.get("task", {}).get("history_scope", "FULL_HISTORY")
        for record in (read(source / "MANIFEST.json"), result))]
    if any(scope not in ("FULL_HISTORY", "VERSION_SCOPED") for scope in scopes):
        raise ValueError("invalid history scope")
    # A caller can restrict the sealed scope, but cannot promote historical evidence.
    history_scope = "VERSION_SCOPED" if "VERSION_SCOPED" in scopes else "FULL_HISTORY"
    if audit.get("status") == "DEV_AUTO_AUDITED" and (audit.get("hard_gate_errors") or len(audit.get("reviews", [])) != 2 or any(
            row.get("validation_errors") or row.get("review", {}).get("verdict") != "ACCEPT"
            for row in audit.get("reviews", []))):
        errors.append("AUDIT_NOT_TWO_VALID_ACCEPTS")
    if result.get("status") != "PASS":
        errors.append("ENGINEERING_FAILURE")
    replays = read(source / "REPLAY.json") if (source / "REPLAY.json").exists() else []
    supplemental_replays = []
    if supplemental_directory is not None:
        directory = Path(supplemental_directory)
        binding = read(directory / "SUPPLEMENTAL_BINDING.json")
        actual = {path.relative_to(directory).as_posix(): sha(path) for path in directory.rglob("*")
            if path.is_file() and path.name != "SUPPLEMENTAL_BINDING.json" and not path.name.endswith(".lock")}
        if binding["source_pair_sha256"] != sha(source / "PAIR.json") or binding["evidence_sha256"] != actual:
            raise ValueError("supplemental replay/source binding changed")
        if [json.loads(line) for line in (directory / "CASES.jsonl").read_text(encoding="utf-8").splitlines()] != read(source / "PAIR.json"):
            raise ValueError("supplemental replay cases differ")
        supplemental_replays = read(directory / "REPLAY.json")
    all_replays = [*replays, *supplemental_replays]
    if len(all_replays) < 6 or any(row.get("passed") is not True for row in all_replays):
        errors.append("STRICT_REPLAY_INCOMPLETE")
    if history_scope != "FULL_HISTORY":
        errors.append("HISTORY_INDETERMINATE")
    if not vector.get("runtime_consumed"):
        errors.append("NO_EXECUTABLE_STRUCTURE")
    audit_status = audit.get("status")
    accepted = audit_status == "DEV_AUTO_AUDITED" and not errors
    state = "DEV_ACCEPTED" if accepted else ("QUARANTINED_HISTORY_INDETERMINATE" if
        "HISTORY_INDETERMINATE" in errors else "REJECTED" if result.get("status") != "PASS" or
        audit_status == "REJECTED" else "QUARANTINED")
    return {"version": VERSION, "status": state, "hard_gate_errors": errors,
        "audit_status": audit_status, "source_result_sha256": sha(source / "RESULT.json"),
        "audit_result_sha256": canonical_sha256(audit), "structural_vector": vector,
        "recorded_strict_replays": len(all_replays), "history_scope": history_scope,
        "same_model_audit_independent_science": False, "formal_accepted": False,
        "new_scientific_families": 0, "machine_qualified": False}
