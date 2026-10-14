"""Freeze observed metadata only; never alter scientific code or accept a campaign."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scientific_closure import (ROOT, RELEASE, FROZEN_VERSIONS, canonical_sha256,
                                read_json, reference, sha256, source_tree_hash, write_new)

BASE = ROOT / "artifacts/scientific_closure_v3_2"
TESTED_MODEL = "deepseek-v4.1-flash"
UNSET = "PROVIDER_DEFAULT_UNSET"


def normalized_parameters(parameters: dict) -> dict:
    return {"explicit_parameters": parameters,
            **{k: parameters.get(k, UNSET) for k in ("temperature", "top_p", "max_tokens", "tool_choice", "response_format")},
            "reasoning_parameters": {k: v for k, v in parameters.items() if "reason" in k or "think" in k} or UNSET}


def summarize_records(results: dict, prior_records: list) -> tuple[dict, dict]:
    """Recompute every retained request; prior hashes are a cross-check, not inputs."""
    prior = {(r["unit_id"], r["record_id"]): r for r in prior_records}
    if len(prior) != len(prior_records):
        raise ValueError("duplicate prior ledger identity")
    actual, roles, profiles = {}, {}, {}
    for unit, result in results.items():
        for record in result["replay"]["model_records"]:
            request, response = record["request"], record["response"]
            role = request["role_metadata"]["role"]
            requested_model = response.get("model_id")
            expected_model = "glm-5.3-flash" if role == "SYNTHETIC_HUMAN" else TESTED_MODEL
            if requested_model != expected_model:
                raise ValueError("recorded role/model identity conflicts with frozen roster")
            fingerprint = {"unit_id": unit, "case_id": result["case_id"], "record_id": record["record_id"], "role": role,
                "request_sha256": canonical_sha256(request),
                "system_prompt_sha256": canonical_sha256([m for m in request["messages"] if m["role"] == "system"]),
                "initial_task_sha256": canonical_sha256(next((m for m in request["messages"] if m["role"] == "user"), None)),
                "tool_schema_sha256": canonical_sha256(request["tools"])}
            key = (unit, record["record_id"])
            if fingerprint["request_sha256"] != record["request_sha256"] or key in actual:
                raise ValueError("changed request or duplicate model record")
            actual[key] = fingerprint
            group = roles.setdefault(role, {"record_count": 0, "role_metadata_hashes": set(), "system_prompt_hashes": set(),
                                           "initial_task_hashes": set(), "tool_schema_hashes": set()})
            group["record_count"] += 1
            group["role_metadata_hashes"].add(canonical_sha256(request["role_metadata"]))
            for field, fingerprint_field in (("system_prompt_hashes", "system_prompt_sha256"), ("initial_task_hashes", "initial_task_sha256"), ("tool_schema_hashes", "tool_schema_sha256")):
                group[field].add(fingerprint[fingerprint_field])
            profile = profiles.setdefault(role, {"role_class": "AUXILIARY_SYNTHETIC_HUMAN" if role == "SYNTHETIC_HUMAN" else "TESTED_AGENT",
                "requested_model_id": requested_model, "provider_returned_model_ids": Counter(), "parameters": Counter()})
            profile["provider_returned_model_ids"][str(response.get("provider_metadata", {}).get("model", "UNKNOWN_NOT_RETAINED"))] += 1
            profile["parameters"][json.dumps(request["parameters"], sort_keys=True)] += 1
    if not actual or actual != prior:
        raise ValueError("retained request coverage/content differs from observed ledger")
    for group in roles.values():
        for key, value in group.items():
            if isinstance(value, set): group[key] = sorted(value)
    for profile in profiles.values():
        profile["provider_returned_model_ids"] = dict(profile["provider_returned_model_ids"])
        profile["parameter_profiles"] = [{"record_count": count, **normalized_parameters(json.loads(p))}
                                         for p, count in sorted(profile.pop("parameters").items())]
    return roles, profiles


def build_documents(binding_path: Path) -> tuple[dict, dict]:
    release = read_json(RELEASE)
    if source_tree_hash(ROOT) != release["source_tree_sha256"]:
        raise ValueError("scientific source changed; cannot freeze a metadata-only addendum")
    observed_path = BASE / "observed-model-profiles-001.json"
    observed = read_json(observed_path)
    binding = read_json(binding_path)
    if binding["base_release"] != reference(RELEASE):
        raise ValueError("binding audit refers to another release")
    by_suite = {s["suite"]: s for s in binding["suites"]}
    observed_by_suite = {s["suite"]: s for s in observed["suites"]}
    if set(by_suite) != set(FROZEN_VERSIONS) or set(observed_by_suite) != set(FROZEN_VERSIONS):
        raise ValueError("incomplete suite coverage")
    prompts, profiles, total = {}, {}, 0
    for suite, version in FROZEN_VERSIONS.items():
        row = observed_by_suite[suite]
        for ref in row["evidence"]:
            if sha256(ROOT / ref["path"]) != ref["sha256"]:
                raise ValueError("observed metadata input changed")
        run_id = f"{TESTED_MODEL}-{suite}-{version}-formal"
        if row["run_id"] != run_id or by_suite[suite]["run_id"] != run_id:
            raise ValueError("suite/run identity mismatch")
        results_path = ROOT / "data/runs" / run_id / "results.json"
        results = read_json(results_path)
        if len(results) != 90: raise ValueError("incomplete retained results")
        roles, role_profiles = summarize_records(results, row["records"])
        count = sum(r["record_count"] for r in roles.values())
        total += count
        prompts[suite] = {"run_id": run_id, "retained_case_count": len(results), "model_record_count": count,
            "simulation_only": suite in {"T361", "T362", "T363"}, "roles": roles,
            "record_ledger": reference(observed_path), "raw_result_evidence": reference(results_path),
            "binding_level": by_suite[suite]["binding_level"], "canonical_accepted": by_suite[suite]["canonical_accepted"],
            "coverage": "PRIMARY_ONLY_PAIRED_BRANCHES_NOT_RETAINED" if suite == "T353" else "RETAINED_TERMINAL_TRAJECTORIES_ONLY"}
        profiles[suite] = {"run_id": run_id, "roles": role_profiles,
            "initial_manifest_concurrency": row["initial_manifest_concurrency"],
            "actual_concurrency_on_each_resume": row["actual_concurrency_on_each_resume"], "evidence": row["evidence"]}
    profile = {"artifact": "OBSERVED_MODEL_PROFILE_ADDENDUM", "frozen": True, "addendum_scope": "provenance_and_metadata_only",
        "base_profile": reference(ROOT / f"release/MODEL_PROFILE_{TESTED_MODEL}.json"),
        "base_release": reference(RELEASE), "canonical_tested_model_roster": [TESTED_MODEL], "provider": "aihubmix",
        "model_record_count": total, "suites": profiles,
        "transport_from_source": observed["source_derived_transport"], "scheduler": observed["scheduler"],
        "tool_calling_behavior_from_source": "AIHubMixAdapter forwards recorded tools when nonempty and omits tools when empty; tool_choice is unset unless explicit in request parameters.",
        "response_format_behavior_from_source": "No response_format is added by the adapter; explicit request parameters are forwarded.",
        "source_evidence": reference(ROOT / "src/ioabench/models/aihubmix.py"),
        "corrections_to_base_profile": ["The base profile's single max_tokens=8192 value does not describe every retained call: T311 uses 4096; synthetic-human calls use 2000.",
            "ModelResponse.model_id copies the requested model ID. Provider-returned aliases are separate metadata, not independent model-identity attestation.",
            "Live model discovery replies/capabilities were not retained; the base profile's live-discovery claim is not independently re-certified here."],
        "canonical_acceptance": False}
    addendum = {"artifact": "BENCHMARK_RELEASE_METADATA_ADDENDUM", "frozen": True,
        "base_release_id": release["release_id"], "base_release_sha256": sha256(RELEASE), "base_release": reference(RELEASE),
        "addendum_scope": "provenance_and_metadata_only", "benchmark_semantics_changed": False,
        "statement": "No runtime, scorer, prompt, tool, dataset, model roster or scientific scoring semantics changed.",
        "scientific_source_sha256": release["source_tree_sha256"], "model_record_count": total, "suites": prompts,
        "hash_definition": {"algorithm": "ioabench.hashing.canonical_sha256",
            "role_metadata": "Complete request.role_metadata mapping; this is identity metadata, not a substitute for system prompt content.",
            "system_prompt": "Ordered list of all request messages whose role is system, including complete message objects.",
            "initial_task": "First complete request message whose role is user, or JSON null if absent.",
            "tool_schema": "Complete ordered request.tools array; empty arrays are hashed explicitly.",
            "request_ledger": "Per-record request/system/initial-task/tool hashes are joined by suite, unit_id and record_id in the referenced ledger; full inputs remain in hash-pinned results."},
        "retroactive_binding_audit": reference(binding_path), "T311_deviation": reference(ROOT / "artifacts/gates/T311_CANONICAL_DEVIATION.json"),
        "scheduler_retry_references": [reference(ROOT / "config/scheduler_profile.json"), reference(ROOT / "artifacts/gates/V32_S1_POLICY_IMPACT_v2.json")],
        "acceptance_effect": "METADATA_ONLY_NO_CANONICAL_UPGRADE", "canonical_acceptance": False,
        "limits": ["Hashes describe retained historical requests; they do not create a new tested-agent scaffold or certify all historical requests equivalent to the base Release.",
            "T353 paired raw records and original invalid attempts are missing and are not represented in the hashes.",
            "Per-call host, actual concurrency on each resume, model discovery responses and context window remain unknown.",
            "The linked binding audit remains NOT_ACCEPTED; T311 deviation remains UNKNOWN."]}
    return profile, addendum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.revision < 1: parser.error("revision must be positive")
    profile_path = ROOT / f"release/MODEL_PROFILE_{TESTED_MODEL}_ADDENDUM_{args.revision}.json"
    addendum_path = ROOT / f"release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_{args.revision}.json"
    validation_path = BASE / f"metadata-addendum-validation-{args.revision:03d}.json"
    if not args.validate_only and any(p.exists() for p in (profile_path, addendum_path, validation_path)):
        raise FileExistsError("addendum revision already exists; preserve it and choose another revision")
    profile, addendum = build_documents(args.binding.resolve())
    if args.validate_only:
        if read_json(profile_path) != profile: raise ValueError("normalized profile differs from source records")
    else:
        write_new(profile_path, profile)
    addendum["normalized_model_profile"] = reference(profile_path)
    if args.validate_only:
        if read_json(addendum_path) != addendum: raise ValueError("metadata addendum differs from source records")
    else:
        write_new(addendum_path, addendum)
        write_new(validation_path, {"artifact": "RELEASE_METADATA_ADDENDUM_VALIDATION", "pass": True,
            "scope": "Exact retained-input metadata and immutable base Release only; canonical eligibility is not granted.",
            "model_records_checked": profile["model_record_count"], "suites_checked": len(profile["suites"]),
            "provider_calls": 0, "canonical_acceptance": False,
            "evidence": [reference(RELEASE), reference(profile_path), reference(addendum_path), reference(Path(__file__))]})
    print(json.dumps({"validated_only": args.validate_only, "metadata_integrity_pass": True,
                      "model_records_checked": profile["model_record_count"], "canonical_acceptance": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
