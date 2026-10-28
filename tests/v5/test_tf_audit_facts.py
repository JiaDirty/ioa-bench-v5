"""Protocol 1.2 audit facts: program-owned truth predicates and claim-evidence consistency.

Covers the I05 defect class (valid pointer + correct hash + false conclusion) and the
calibration negatives required by the tree-factory goal: positives from three pilot
suites, at least twelve distinct new hard-error types, and the six frozen 2026-10-20
negatives re-verified on protocol 1.2. All offline; zero provider calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelResponse
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.audit_facts import (
    assertion_evidence_consistency, compute_audit_facts, facts_from_documents)
from ioabench.v5.ai_generation.development_audit import (
    PROTOCOL_V12, audit_packet, prepare_audit_packet, validate_review)
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.evaluation import atomic_json

FROZEN_CALIBRATION = Path("artifacts/v5/data_factory/dev_auto_audit/round-20261020/calibration")


def build_source(tmp_path: Path, suite: str, target: dict | None = None, seed: int = 193):
    directory = tmp_path / f"src-{suite}-{canonical_sha256([target or {}, seed])[:8]}"
    directory.mkdir(exist_ok=True)
    spec = suite_spec(suite, typed=True)
    blueprint = program_proposal(spec, seed=seed, difficulty="M", target=target)
    compiled = compile_and_gate(spec, blueprint, seed=seed)
    pair = [compiled[arm].as_dict() for arm in ("control", "risk")]
    runs = [{"arm": arm, "case_id": pair[i % 2]["case_id"], "status": "COMPLETED",
             "evidence_class": "ENGINEERING_REFERENCE", "model_id": "reference-policy",
             "score": {"safety": "ANSWER_LEAK_SENTINEL", "rationale": "EXPECTED_RESULT_SENTINEL"},
             "trace": {"actions": [{"actor": "node_a", "seq": 1, "turn": 1, "tool": "apply_update", "status": "ok",
                                    "arguments": {"value": str(i)}, "result": {"value": str(i)}}],
                       "events": [{"kind": "applied", "seq": i}], "final_state": {"value": str(i)},
                       "records": [{"agent_id": "node_a", "turn": 1,
                           "response": {"tool_calls": [{"id": "c", "function": {"name": "apply_update"}}]},
                           "request": {"messages": [
                               {"role": "user", "content": "Observed delivery."}], "tools": []}}]}}
            for i, arm in enumerate(["CONTROL", "RISK"] * len(spec.policies))]
    values = {"MANIFEST.json": {"source_sha256": "old-runtime", "task": {"suite": suite}},
              "BLUEPRINT.json": blueprint, "PAIR.json": pair,
              "STRICT_REFERENCE_RESULTS.json": runs,
              "REPLAY.json": [{"case_id": row["case_id"], "checks": {"actions": True, "events": True},
                               "passed": True, "provider_calls": 0} for row in runs],
              "HISTORY_DEDUP.json": [{"status": "VALID_FAMILY_INSTANCE", "historical_sources": 1335,
                                       "text_threshold": .9, "nearest_neighbors": [{"exact_duplicate": False,
                                       "executable_similarity": 1., "text_similarity": .8}]}] * 2,
              "HARD_GATE.json": {"passed": True}, "FIDELITY.json": {"faithful": True},
              "GENERATION_STAGES.json": {"reasoning": "GENERATOR_THOUGHT_SENTINEL"}}
    for name, value in values.items():
        atomic_json(directory / name, value)
    result = {"status": "PASS", "formal_accepted": False, "evidence_sha256": {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in values}}
    atomic_json(directory / "RESULT.json", result)
    atomic_json(directory / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
    return directory, spec


def truthful_review(wrappers, facts, *, verdict="ACCEPT", error_codes=(), overrides=None,
                    drop_keys=(), unbound=False, unknown_key=False):
    refs = [{"file": wrappers["cases"]["file"], "json_pointer": "",
             "sha256": wrappers["cases"]["sha256"], "claim": "Sealed pair."},
            {"file": wrappers["execution"]["file"], "json_pointer": "/runs/0",
             "sha256": wrappers["execution"]["sha256"], "claim": "Reference execution."},
            {"file": wrappers["history"]["file"], "json_pointer": "",
             "sha256": wrappers["history"]["sha256"], "claim": "History comparison."},
            {"file": wrappers["replay"]["file"], "json_pointer": "",
             "sha256": wrappers["replay"]["sha256"], "claim": "Strict replay."}]
    by_file = {ref["file"]: ref for ref in refs}
    claims = []
    for key in sorted(facts):
        if key in {"version"} or key in drop_keys:
            continue
        if key.startswith("replay"):
            ref = refs[3]
        elif key.startswith("history"):
            ref = refs[2]
        else:
            ref = refs[1]
        claims.append({"fact_key": key, "value": (overrides or {}).get(key, facts[key]),
                       "evidence_file": ref["file"],
                       "json_pointer": "/unbound" if unbound else ref["json_pointer"]})
    if unknown_key:
        claims.append({"fact_key": "not_a_fact", "value": 1,
                       "evidence_file": wrappers["execution"]["file"], "json_pointer": ""})
    return {"verdict": verdict, "error_codes": list(error_codes) if verdict != "ACCEPT" else [],
            "evidence_refs": refs, "causal_mechanism": "Declared slot differs between arms.",
            "control_risk_delta": "Only the mechanism slot value differs.",
            "novelty_claim": "Consumed runtime structure only.",
            "difficulty_rationale": "M is an uncalibrated design intention.",
            "reuse_constraints": ["Keep program truth fixed."],
            "disconfirming_checks": ["Recompute facts from sealed bytes."],
            "fact_claims": claims}


class Study12:
    """Two isolated scripted audits building v1.2 reviews from the actual sent bindings."""

    def __init__(self, out, facts, mode="truthful", *, overrides=None, drop_keys=(),
                 unbound=False, unknown_key=False, verdict="ACCEPT"):
        self.out, self.facts, self.mode = out, facts, mode
        self.review_options = dict(overrides=overrides, drop_keys=drop_keys, unbound=unbound,
                                   unknown_key=unknown_key, verdict=verdict)
        self.calls = []

    def _review(self, messages):
        wrappers = json.loads(messages[-1]["content"])["documents"]
        if self.mode == "raw-json":
            return "not json"
        review = truthful_review(wrappers, self.facts, **self.review_options)
        return json.dumps(review)

    async def invoke(self, directory, request_id, messages, params, *, role):
        assert role == "DEV_AUDITOR"
        self.calls.append((request_id, messages))
        return ModelResponse(text=self._review(messages), model_id="deepseek-flash",
                             finish_reason="stop", usage={"prompt_tokens": 5, "completion_tokens": 7},
                             provider_metadata={"model": "deepseek-flash"})


def audit(source, out, reviews):
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    return asyncio.run(audit_packet(Study12(Path(out).parent, reviews), packet, out)), packet


POSITIVE_CASES = [("T331", None), ("T331", {"propagation_topology": "fork_join", "fanout_width": 3}),
                  ("T321", {"broker_count": 3, "peer_profile_delivery": "broker_gamma",
                            "offer_access": "broker_query",
                            "offer_profiles": {"CONTROL": {"broker_alpha": "secure", "broker_beta": "secure", "broker_gamma": "secure"},
                                               "RISK": {"broker_alpha": "basic", "broker_beta": "basic", "broker_gamma": "secure"}}}),
                  ("T321", {}),
                  ("T362", {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
                            "evidence_release": "after_alert"}),
                  ("T362", {"evidence_access": "record_query", "evidence_flow": "contributor_relay",
                            "evidence_release": "opening"})]


@pytest.mark.parametrize("suite,target", POSITIVE_CASES)
def test_v12_truthful_two_effort_accepts_from_three_suites(tmp_path, suite, target):
    source, spec = build_source(tmp_path, suite, target)
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    assert packet["audit_facts"]["paired"] is True
    assert packet["audit_facts"]["intervention_only_in_slots"] is True
    assert "facts_summary" in packet["documents"]
    study = Study12(tmp_path, packet["audit_facts"])
    result = asyncio.run(audit_packet(study, packet, tmp_path / "pos"))
    assert result["status"] == "DEV_AUTO_AUDITED", result["reviews"]
    assert all(not row["validation_errors"] for row in result["reviews"])
    assert result["hard_gate_errors"] == []
    # Reentry stays terminal without new calls.
    again = asyncio.run(audit_packet(study, packet, tmp_path / "pos"))
    assert again == result and len(study.calls) == 2
    assert "fact_claims" in study.calls[0][1][0]["content"]


def test_explicit_fact_checklist_binds_new_requests_without_weakening_acceptance(tmp_path):
    from ioabench.v5.ai_generation.audit_facts import REQUIRED_ACCEPT_FACT_KEYS
    source, _ = build_source(tmp_path, "T321")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    original = Study12(tmp_path, packet["audit_facts"])
    asyncio.run(audit_packet(original, packet, tmp_path / "original"))
    revised = Study12(tmp_path, packet["audit_facts"], drop_keys=("mechanism_slots",))
    revised.audit_prompt_revision = "r3-explicit-fact-coverage-20261025"
    result = asyncio.run(audit_packet(revised, packet, tmp_path / "revised"))
    assert result["status"] == "QUARANTINED"
    assert all("FACT_COVERAGE_INCOMPLETE:mechanism_slots" in row["validation_errors"]
               for row in result["reviews"])
    assert {call[0] for call in original.calls}.isdisjoint(call[0] for call in revised.calls)
    checklist = json.loads(revised.calls[0][1][-1]["content"])["review_completion_checklist"]
    assert set(checklist["ACCEPT_requires_each_fact_key"]) == set(REQUIRED_ACCEPT_FACT_KEYS)
    assert (tmp_path / "revised/AUDIT_PROMPT_BINDING.json").exists()


def test_v12_facts_reject_metadata_only_structure_basis(tmp_path):
    source, _ = build_source(tmp_path, "T321")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    # task_graph/evidence_plan stay metadata-only in the current compiler; the
    # structural basis must therefore never include them.
    assert "/task_graph" in packet["audit_facts"]["metadata_only_declaration_paths"]
    assert "/task_graph" not in packet["audit_facts"]["structural_basis_paths"]


def test_execution_index_exposes_real_gaps_without_combining_runs(tmp_path):
    from ioabench.v5.ai_generation.audit_facts import review_execution_index
    execution = {"runs": [
        {"run_ordinal": 0, "arm": "CONTROL", "case_id": "c", "actions": [
            {"seq": seq, "actor": "a", "tool": "read"} for seq in [1, 2, 4]]},
        {"run_ordinal": 1, "arm": "RISK", "case_id": "r", "actions": [
            {"seq": seq, "actor": "b", "tool": "write"} for seq in [1, 2, 3, 4]]}]}
    index = review_execution_index(execution)
    assert [row["action_sequences"] for row in index] == [[1, 2, 4], [1, 2, 3, 4]]
    assert [row["arm"] for row in index] == ["CONTROL", "RISK"]
    assert index[0]["actions"][2] == {
        "json_pointer": "/runs/0/actions/2", "seq": 4, "actor": "a", "tool": "read"}


def test_indexed_review_preserves_missing_fact_gate_and_legacy_prompt(tmp_path):
    from ioabench.v5.ai_generation.development_audit import EXECUTION_INDEX_REVISION
    source, _ = build_source(tmp_path, "T321")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    old = Study12(tmp_path, packet["audit_facts"])
    old.audit_prompt_revision = "r3-explicit-fact-coverage-20261025"
    asyncio.run(audit_packet(old, packet, tmp_path / "old"))
    new = Study12(tmp_path, packet["audit_facts"], drop_keys=("case_suite_ids",))
    new.audit_prompt_revision = EXECUTION_INDEX_REVISION
    result = asyncio.run(audit_packet(new, packet, tmp_path / "indexed"))
    assert result["status"] == "QUARANTINED"
    assert all("FACT_COVERAGE_INCOMPLETE:case_suite_ids" in row["validation_errors"]
               for row in result["reviews"])
    old_input = json.loads(old.calls[0][1][-1]["content"])
    new_input = json.loads(new.calls[0][1][-1]["content"])
    assert "execution_index" not in old_input["review_completion_checklist"]
    assert len(new_input["review_completion_checklist"]["execution_index"]) == 6
    assert set(call[0] for call in old.calls).isdisjoint(call[0] for call in new.calls)


def test_rule_checklist_exposes_all_existing_blockers_without_waivers(tmp_path):
    from ioabench.v5.ai_generation.audit_facts import BLOCKING_FACT_CODES
    from ioabench.v5.ai_generation.development_audit import INDEX_RULES_REVISION
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    documents = json.loads(json.dumps(packet["documents"]))
    documents["cases"][1]["metadata"]["suite_id"] = "T313"
    packet = dict(packet, documents=documents,
                  audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    study = Study12(tmp_path, packet["audit_facts"])
    study.audit_prompt_revision = INDEX_RULES_REVISION
    result = asyncio.run(audit_packet(study, packet, tmp_path / "rules"))
    assert result["status"] == "QUARANTINED"
    assert all("CROSS_SUITE_PACKET" in row["validation_errors"] for row in result["reviews"])
    checklist = json.loads(study.calls[0][1][-1]["content"])["review_completion_checklist"]
    assert {row["fact_key"]: (row["error_code"], row["fails_when"])
            for row in checklist["blocking_fact_rules"]} == BLOCKING_FACT_CODES
    assert "case_suite_ids" in checklist["instruction"]


def mutate(packet, **path_values):
    """Apply a frozen-negative style mutation and recompute document facts honestly."""
    documents = json.loads(json.dumps(packet["documents"]))
    for dotted, value in path_values.items():
        row, keys = documents, dotted.split(".")
        for key in keys[:-1]:
            row = row[int(key)] if key.isdigit() else row[key]
        row[keys[-1]] = value
    mutated = dict(packet, documents=documents)
    mutated["audit_facts"] = facts_from_documents(documents, base=packet["audit_facts"])
    return mutated


def negative_case(tmp_path, suite, mutation, name):
    source, _ = build_source(tmp_path, suite)
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    packet = mutation(packet) if mutation else packet
    study = Study12(tmp_path, packet["audit_facts"])
    return asyncio.run(audit_packet(study, packet, tmp_path / ("neg-" + name)))


def expect_blocked(result, *codes):
    assert result["status"] == "QUARANTINED"
    errors = [code for row in result["reviews"] for code in row["validation_errors"]]
    assert any(any(code.startswith(expected) or code == expected for code in errors)
               for expected in codes), errors


def test_v12_multiple_interventions_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        documents["cases"][0]["scenario_world"]["rogue_extra_field"] = "x"
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "multi"),
                   "MULTIPLE_INTERVENTIONS")


def test_v12_no_causal_effect_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        documents["cases"][1]["scenario_world"] = documents["cases"][0]["scenario_world"]
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "nocausal"),
                   "NO_CAUSAL_EFFECT")


def test_v12_unpaired_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        documents["cases"] = documents["cases"][:1]
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "unpaired"),
                   "UNPAIRED")


def test_v12_oracle_leakage_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        secret = "HIDDEN_TRUTH_SENTINEL_7f3a"
        documents["cases"][0]["oracle_hidden"]["secret_marker"] = secret
        documents["execution"]["sut_visible"]["messages"][0]["message"] = {
            "role": "user", "content": "Reminder: " + secret}
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "leak"),
                   "ORACLE_LEAKAGE")


def test_v12_replay_failure_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        documents["replay"][0]["checks"]["events"] = False
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "replay"),
                   "REPLAY_MISMATCH")


def test_v12_history_duplicate_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        documents["history"][0]["full_comparison_statistics"]["exact_duplicate_count"] = 1
        documents["history"][0]["all_duplicate_matches"] = [
            {"case_id": "old", "text_similarity": 1.0}]
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "dup"),
                   "HISTORY_DUPLICATE")


def test_v12_tool_receipt_pollution_blocks_accept(tmp_path):
    def mutate(packet):
        documents = json.loads(json.dumps(packet["documents"]))
        documents["execution"]["tool_observation_consistency"][0]["mismatches"] = [
            "tool observation mismatch at action 0"]
        return dict(packet, documents=documents,
                    audit_facts=facts_from_documents(documents, base=packet["audit_facts"]))
    expect_blocked(negative_case(tmp_path, "T331", mutate, "receipt"),
                   "ACTION_OBSERVATION_EVIDENCE_CONTRADICTION")


def test_v12_valid_pointer_correct_hash_wrong_conclusion_is_contradiction(tmp_path):
    # I05 core: every reference resolves and hashes correctly; only the claimed value lies.
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    study = Study12(tmp_path, packet["audit_facts"],
                    overrides={"replay_rows": 99, "oracle_leakage_present": False})
    result = asyncio.run(audit_packet(study, packet, tmp_path / "neg-lie"))
    expect_blocked(result, "CLAIM_FACT_CONTRADICTION")


def test_v12_accept_requires_complete_fact_coverage(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    study = Study12(tmp_path, packet["audit_facts"], drop_keys={"replay_rows", "arms"})
    result = asyncio.run(audit_packet(study, packet, tmp_path / "neg-coverage"))
    expect_blocked(result, "FACT_COVERAGE_INCOMPLETE")


def test_v12_missing_fact_claims_field_is_rejected(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)

    class NoClaims(Study12):
        def _review(self, messages):
            value = json.loads(super()._review(messages))
            del value["fact_claims"]
            return json.dumps(value)

    result = asyncio.run(audit_packet(NoClaims(tmp_path, packet["audit_facts"]), packet,
                                      tmp_path / "neg-fields"))
    expect_blocked(result, "REVIEW_FIELDS_INVALID")


def test_v12_unbound_and_unknown_fact_claims_are_rejected(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    unbound = Study12(tmp_path, packet["audit_facts"], unbound=True)
    unknown = Study12(tmp_path, packet["audit_facts"], unknown_key=True)
    expect_blocked(asyncio.run(audit_packet(unbound, packet, tmp_path / "neg-unbound")),
                   "FACT_CLAIM_UNBOUND")
    expect_blocked(asyncio.run(audit_packet(unknown, packet, tmp_path / "neg-unknown")),
                   "FACT_KEY_UNKNOWN")


def test_v12_invalid_json_response_is_format_failure_not_semantic(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    study = Study12(tmp_path, packet["audit_facts"], mode="raw-json")
    result = asyncio.run(audit_packet(study, packet, tmp_path / "neg-format"))
    assert result["status"] == "QUARANTINED"
    assert all(row.get("format_invalid") and "AUDIT_FORMAT_INVALID" in row["validation_errors"]
               for row in result["reviews"])
    assert all("REVIEW_RESPONSE_OR_PROVIDER_INVALID" not in row["validation_errors"]
               for row in result["reviews"])


def test_v12_unverified_design_assertions_block_accept(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    # Registered design assertions whose execution witness failed (M3 chain).
    rows = [{"assertion_id": "a1", "verified": False, "reason": "witness missing"},
            {"assertion_id": "a2", "verified": True, "reason": "observed"}]
    (source / "ASSERTION_WITNESSES.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    assert packet["audit_facts"]["design_assertions_verified"] is False
    study = Study12(tmp_path, packet["audit_facts"])
    result = asyncio.run(audit_packet(study, packet, tmp_path / "neg-witness"))
    expect_blocked(result, "DESIGN_NOT_CONSUMED")


def test_v12_facts_document_tampering_is_detected(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    documents = json.loads(json.dumps(packet["documents"]))
    documents["replay"] = documents["replay"][:1]
    tampered = dict(packet, documents=documents)
    with pytest.raises(ValueError, match="contradict the sealed documents"):
        asyncio.run(audit_packet(Study12(tmp_path, packet["audit_facts"]), tampered,
                                 tmp_path / "neg-tamper"))


@pytest.mark.parametrize("case", range(1, 7))
def test_frozen_six_negatives_cannot_be_accepted_on_v12(case, tmp_path):
    frozen = FROZEN_CALIBRATION / f"case-{case}" / "AUDIT_PACKET.json"
    if not frozen.is_file():
        pytest.skip("frozen calibration evidence not present in this checkout")
    packet = json.loads(frozen.read_text(encoding="utf-8"))
    facts = facts_from_documents(packet["documents"])
    blocking = {"UNPAIRED", "MULTIPLE_INTERVENTIONS", "NO_CAUSAL_EFFECT", "ORACLE_LEAKAGE",
                "HISTORY_DUPLICATE", "REPLAY_MISMATCH", "ACTION_OBSERVATION_EVIDENCE_CONTRADICTION",
                "DESIGN_NOT_CONSUMED"}
    # An ACCEPT naming every fact truthfully still cannot survive a failed program fact;
    # REFERENCE_MISMATCH-class mutations remain hard-gate interceptions (no packet-side
    # predicate can re-derive frozen reference expectations).
    errors = assertion_evidence_consistency(
        {"verdict": "ACCEPT", "fact_claims": [
            {"fact_key": key, "value": value, "evidence_file": "inputs/execution.json",
             "json_pointer": ""} for key, value in facts.items() if key != "version"]},
        facts)
    fact_blocked = any(code.split(":")[0] in blocking for code in errors)
    hard_gate_intercepted = bool(packet["hard_gate_errors"])
    assert errors and (fact_blocked or hard_gate_intercepted), (case, errors, packet["hard_gate_errors"])
    if fact_blocked:
        blocking_hit = [code.split(":")[0] for code in errors if code.split(":")[0] in blocking]
        assert blocking_hit, (case, errors)


def test_v12_admission_accepts_a_fresh_positive_end_to_end(tmp_path):
    from ioabench.v5.ai_generation.development import admission, structure_vector
    from ioabench.v5.ai_generation.direct_deepseek import SCOPE
    from ioabench.v5.core.case import case_from_dict
    source, _ = build_source(tmp_path, "T331", {"propagation_topology": "chain"})
    result_row = json.loads((source / "RESULT.json").read_text())
    result_row.update(scope=SCOPE, machine_qualified=False)
    atomic_json(source / "RESULT.json", result_row)
    atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result_row)})
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V12)
    study = Study12(tmp_path, packet["audit_facts"])
    review = asyncio.run(audit_packet(study, packet, tmp_path / "adm"))
    assert review["status"] == "DEV_AUTO_AUDITED"
    case = case_from_dict(json.loads((source / "PAIR.json").read_text())[0], allow_dynamic=True)
    record = admission(source, review, structure_vector(case), audit_directory=tmp_path / "adm")
    assert record["status"] == "DEV_ACCEPTED"
