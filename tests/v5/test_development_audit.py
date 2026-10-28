from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from ioabench.errors import ProviderRequestUnresolved
from ioabench.hashing import canonical_sha256
from ioabench.models import ModelResponse
from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.development_audit import audit_pair, audit_packet, prepare_audit_packet
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.evaluation import atomic_json


@pytest.fixture
def source(tmp_path, request):
    directory = tmp_path / "old-source"
    directory.mkdir()
    selected_suite = getattr(request, "param", "T331")
    spec = suite_spec(selected_suite, typed=True)
    blueprint = program_proposal(spec, seed=193, difficulty="M")
    compiled = compile_and_gate(spec, blueprint, seed=193)
    pair = [compiled[arm].as_dict() for arm in ("control", "risk")]
    runs = [{"arm": arm, "case_id": pair[i % 2]["case_id"], "status": "COMPLETED",
             "score": {"safety": "ANSWER_LEAK_SENTINEL", "rationale": "EXPECTED_RESULT_SENTINEL"},
             "trace": {"actions": [{"actor": "node_a", "seq": 1, "turn": 1, "tool": "apply_update", "arguments": {"value": str(i)}, "result": {"value": str(i)}}],
                       "events": [{"kind": "applied", "seq": i}], "final_state": {"value": str(i)},
                       "records": [{"agent_id": "node_a", "turn": 1,
                           "response": {"tool_calls": [{"id": "c", "function": {"name": "apply_update"}}]},
                           "request": {"messages": [
                           {"role": "user", "content": "Observed delivery."}], "tools": []}}]}}
            for i, arm in enumerate(["CONTROL", "RISK"] * len(spec.policies))]
    values = {"MANIFEST.json": {"source_sha256": "old-runtime", "task": {"suite": selected_suite}},
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
    return directory


class Study:
    def __init__(self, out, verdicts=("ACCEPT", "ACCEPT"), bad_ref=None, fail=None):
        self.out, self.verdicts, self.bad_ref, self.fail = out, verdicts, bad_ref, fail
        self.calls = []

    async def invoke(self, directory, request_id, messages, params, *, role):
        assert role == "DEV_AUDITOR"
        self.calls.append((directory, request_id, messages, params))
        if self.fail:
            raise self.fail
        docs = json.loads(messages[-1]["content"])["documents"]
        refs = [{"file": item["file"], "json_pointer": "", "sha256": item["sha256"],
                 "claim": "Actual bound evidence."} for item in docs.values()]
        if self.bad_ref:
            refs[0].update(self.bad_ref)
        verdict = self.verdicts[len(self.calls) - 1]
        value = {"verdict": verdict, "error_codes": [] if verdict == "ACCEPT" else ["NO_CAUSAL_EFFECT"],
                 "evidence_refs": refs, "causal_mechanism": "Changed inbound update enters downstream state.",
                 "control_risk_delta": "One inbound value differs.", "novelty_claim": "Existing mechanism instance.",
                 "difficulty_rationale": "M is an uncalibrated design intention.",
                 "reuse_constraints": ["Keep authoritative ledger access fixed."],
                 "disconfirming_checks": ["Compare both arm values against the external source ledger."]}
        return ModelResponse(text=json.dumps(value), model_id="deepseek-flash", finish_reason="stop",
                             usage={"prompt_tokens": 8, "completion_tokens": 9},
                             provider_metadata={"model": "deepseek-flash"})


def run(study, source, out):
    return asyncio.run(audit_pair(study, source, out))


def test_two_isolated_audits_blind_inputs_bound_refs_and_zero_send_resume(tmp_path, source):
    study = Study(tmp_path)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    result = run(study, source, tmp_path / "audit")
    assert result["status"] == "DEV_AUTO_AUDITED"
    assert result["formal_accepted"] is False and result["same_model_audit_independent_science"] is False
    assert len(study.calls) == 2
    assert study.calls[0][1] != study.calls[1][1]
    assert [call[3]["reasoning_effort"] for call in study.calls] == ["high", "max"]
    assert all([message["role"] for message in call[2]] == ["system", "user"] for call in study.calls)
    for call in study.calls:
        sent = json.dumps(call[2])
        for hidden in ("ANSWER_LEAK_SENTINEL", "EXPECTED_RESULT_SENTINEL", "GENERATOR_THOUGHT_SENTINEL",
                       "hard_gate_errors", "old-runtime"):
            assert hidden not in sent
        assert "oracle_hidden" in sent and "sut_visible" in sent
    assert run(study, source, tmp_path / "audit") == result and len(study.calls) == 2
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before


@pytest.mark.parametrize('unclassified,calls,category', [(True, 1, 'UNKNOWN'), (False, 2, 'RESPONSE_PARSE')])
def test_unknown_provider_terminal_stops_but_complete_invalid_json_remains_a_protocol_failure(tmp_path, source, unclassified, calls, category):
    from ioabench.v5.ai_generation.direct_deepseek import DirectStudy
    class Port:
        base_url = 'https://api.deepseek.com'
        def __init__(self):
            self.calls = 0
        async def generate(self, profile, request):
            self.calls += 1
            if unclassified:
                raise RuntimeError('unclassified provider fault')
            return ModelResponse(text='[]', model_id='deepseek-flash', finish_reason='stop',
                usage={'prompt_tokens': 10, 'completion_tokens': 4}, provider_metadata={'model': 'deepseek-flash'})
    port = Port()
    study = DirectStudy(tmp_path, port, [{'id': 'deepseek-flash'}])
    result = run(study, source, tmp_path / 'protocol-audit')
    assert result['status'] == 'QUARANTINED' and port.calls == calls
    assert all(row['provider_category'] == category for row in result['reviews'])
    assert study.stop.exists() is unclassified


def test_history_summary_preserves_all_comparison_risks_and_schema_correspondence(tmp_path, source):
    from ioabench.v5.ai_generation.development_audit import _history_facts
    rows = [{"reference_index": i, "executable_similarity": 1 - i / 100,
             "text_similarity": i / 10, "dimensions": ["edge"] if i < 7 else [],
             "exact_duplicate": i == 8, "runtime_verified": i != 4} for i in range(10)]
    facts = _history_facts({"nearest_neighbors": rows, "text_threshold": .9})
    stats = facts["full_comparison_statistics"]
    assert facts["full_comparison_count"] == 10 and facts["full_comparison_sha256"] == canonical_sha256(rows)
    assert stats["exact_duplicate_count"] == stats["no_dimension_near_duplicate_count"] == stats["unverified_runtime_count"] == 1
    assert {row["reference_index"] for row in facts["all_duplicate_matches"]} == {8, 9}
    packet = prepare_audit_packet(source)
    schema = packet["documents"]["schema"]
    assert schema["blueprint_data"]["suite_id"] == "T331" and "properties" in schema["blueprint_schema"]
    assert "replay" in schema["review_rules"]


def test_candidate_structure_requires_explicit_valid_development_policy(source):
    import yaml

    def reseal():
        result = json.loads((source / "RESULT.json").read_text())
        result["evidence_sha256"] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                                      for name in result["evidence_sha256"]}
        atomic_json(source / "RESULT.json", result)
        atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})

    history = json.loads((source / "HISTORY_DEDUP.json").read_text())
    for row in history:
        row["status"] = "CANDIDATE_NEW_FAMILY"
    atomic_json(source / "HISTORY_DEDUP.json", history)
    reseal()
    assert "FULL_HISTORY_NONDUPLICATE_NOT_PROVEN" in prepare_audit_packet(source)["hard_gate_errors"]
    manifest = json.loads((source / "MANIFEST.json").read_text())
    config = Path(__file__).resolve().parents[2] / "config/v5/deepseek_development_policy_v1.yaml"
    manifest["development_policy"] = yaml.safe_load(config.read_text(encoding="utf-8"))
    atomic_json(source / "MANIFEST.json", manifest)
    reseal()
    assert not prepare_audit_packet(source)["hard_gate_errors"]
    manifest["development_policy"]["formal_scientific_claims"] = True
    atomic_json(source / "MANIFEST.json", manifest)
    reseal()
    with pytest.raises(ValueError, match="invalid opt-in"):
        prepare_audit_packet(source)


@pytest.mark.parametrize("bad_ref", [{"json_pointer": "/missing/path"}, {"sha256": "0" * 64},
                                    {"file": "../outside.json"}, {"json_pointer": "/-1"}])
def test_fabricated_evidence_is_quarantined_not_repaired(tmp_path, source, bad_ref):
    study = Study(tmp_path, bad_ref=bad_ref)
    result = run(study, source, tmp_path / "audit")
    assert result["status"] == "QUARANTINED" and len(study.calls) == 2
    assert all("EVIDENCE_REF_INVALID" in row["validation_errors"] for row in result["reviews"])
    run(study, source, tmp_path / "audit")
    assert len(study.calls) == 2


@pytest.mark.parametrize("verdicts,status", [(("ACCEPT", "REJECT"), "QUARANTINED"),
                                            (("REJECT", "REJECT"), "REJECTED"),
                                            (("UNCERTAIN", "UNCERTAIN"), "QUARANTINED")])
def test_review_disagreement_and_rejection_are_terminal(tmp_path, source, verdicts, status):
    study = Study(tmp_path, verdicts)
    assert run(study, source, tmp_path / "audit")["status"] == status
    run(study, source, tmp_path / "audit")
    assert len(study.calls) == 2


@pytest.mark.parametrize("code", ["ORACLE_LEAKAGE", "UNPAIRED", "HISTORY_DUPLICATE", "NO_CAUSAL_EFFECT",
                                  "REFERENCE_MISMATCH", "REPLAY_MISMATCH"])
def test_calibration_private_hard_gate_cannot_be_outvoted_or_leak_expected_outcome(tmp_path, source, code):
    packet = prepare_audit_packet(source)
    packet["hard_gate_errors"] = [code]
    # Freeze a changed observation without labelling it as a negative in model input.
    packet["documents"]["execution"]["runs"][0]["actions"] = []
    study = Study(tmp_path)
    result = asyncio.run(audit_packet(study, packet, tmp_path / "calibration"))
    assert result["status"] == "QUARANTINED" and result["hard_gate_errors"] == [code]
    assert all(code not in call[2][-1]["content"] for call in study.calls)
    assert result["engineering_status"] == "HARD_GATE_NOT_SATISFIED"


def test_unknown_stops_second_audit_and_terminal_reentry(tmp_path, source):
    study = Study(tmp_path, fail=ProviderRequestUnresolved("sent but response terminal unknown"))
    first = run(study, source, tmp_path / "audit")
    assert first["status"] == "QUARANTINED" and len(study.calls) == 1
    assert first["reviews"][0]["provider_category"] == "REQUEST_UNRESOLVED"
    assert run(study, source, tmp_path / "audit") == first and len(study.calls) == 1


def test_source_and_terminal_tampering_refuse_reentry(tmp_path, source):
    study = Study(tmp_path)
    run(study, source, tmp_path / "audit")
    path = source / "PAIR.json"
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="source binding"):
        run(study, source, tmp_path / "audit")
    path.write_bytes(original)
    path = tmp_path / "audit/inputs/cases.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="terminal evidence"):
        run(study, source, tmp_path / "audit")
    assert len(study.calls) == 2


def test_pool_admission_binds_audit_to_exact_source_and_rejects_forged_verdict(tmp_path, source):
    from copy import deepcopy
    import shutil
    from ioabench.v5.ai_generation.development import admission, structure_vector
    from ioabench.v5.ai_generation.direct_deepseek import SCOPE
    from ioabench.v5.core.case import case_from_dict
    result = json.loads((source / "RESULT.json").read_text())
    result.update(scope=SCOPE, machine_qualified=False)
    atomic_json(source / "RESULT.json", result)
    atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
    study = Study(tmp_path)
    review = run(study, source, tmp_path / "audit-pool")
    case = case_from_dict(json.loads((source / "PAIR.json").read_text())[0], allow_dynamic=True)
    vector = structure_vector(case)
    assert admission(source, review, vector, audit_directory=tmp_path / "audit-pool")["status"] == "DEV_ACCEPTED"
    forged = deepcopy(review)
    forged["hard_gate_errors"] = ["NO_CAUSAL_EFFECT"]
    with pytest.raises(ValueError, match="different source or terminal"):
        admission(source, forged, vector, audit_directory=tmp_path / "audit-pool")
    other = tmp_path / "other-source"
    shutil.copytree(source, other)
    with pytest.raises(ValueError, match="terminal evidence changed"):
        admission(other, review, vector, audit_directory=tmp_path / "audit-pool")


@pytest.mark.parametrize("source,manifest_scope,result_scope,requested_scope,expected_scope", [
    ("T322", "VERSION_SCOPED", "VERSION_SCOPED", None, "VERSION_SCOPED"),
    ("T322", "VERSION_SCOPED", "VERSION_SCOPED", "FULL_HISTORY", "VERSION_SCOPED"),
    ("T322", "VERSION_SCOPED", "VERSION_SCOPED", "VERSION_SCOPED", "VERSION_SCOPED"),
    ("T322", "VERSION_SCOPED", "FULL_HISTORY", "FULL_HISTORY", "VERSION_SCOPED"),
    ("T322", "FULL_HISTORY", "VERSION_SCOPED", "FULL_HISTORY", "VERSION_SCOPED"),
    ("T331", "FULL_HISTORY", "FULL_HISTORY", None, "FULL_HISTORY"),
    ("T331", "FULL_HISTORY", "FULL_HISTORY", "FULL_HISTORY", "FULL_HISTORY"),
    ("T331", "FULL_HISTORY", "FULL_HISTORY", "VERSION_SCOPED", "VERSION_SCOPED"),
], indirect=["source"])
def test_admission_cannot_promote_sealed_history_scope(tmp_path, source, manifest_scope, result_scope, requested_scope, expected_scope):
    from ioabench.v5.ai_generation.development import admission, structure_vector
    from ioabench.v5.ai_generation.direct_deepseek import SCOPE
    from ioabench.v5.core.case import case_from_dict
    manifest = json.loads((source / "MANIFEST.json").read_text())
    manifest["task"]["history_scope"] = manifest_scope
    atomic_json(source / "MANIFEST.json", manifest)
    result = json.loads((source / "RESULT.json").read_text())
    result.update(scope=SCOPE, machine_qualified=False, task={**manifest["task"], "history_scope": result_scope})
    result["evidence_sha256"]["MANIFEST.json"] = hashlib.sha256((source / "MANIFEST.json").read_bytes()).hexdigest()
    atomic_json(source / "RESULT.json", result)
    atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
    before = {path: path.read_bytes() for path in source.iterdir() if path.is_file()}
    study = Study(tmp_path)
    review = run(study, source, tmp_path / "audit-history-scope")
    assert review["status"] == "DEV_AUTO_AUDITED" and len(study.calls) == 2
    control = case_from_dict(json.loads((source / "PAIR.json").read_text())[0], allow_dynamic=True)
    kwargs = {} if requested_scope is None else {"history_scope": requested_scope}
    record = admission(source, review, structure_vector(control), audit_directory=tmp_path / "audit-history-scope", **kwargs)
    assert record["history_scope"] == expected_scope
    if expected_scope == "VERSION_SCOPED":
        assert record["status"] == "QUARANTINED_HISTORY_INDETERMINATE"
        assert "HISTORY_INDETERMINATE" in record["hard_gate_errors"]
    else:
        assert record["status"] == "DEV_ACCEPTED" and not record["hard_gate_errors"]
    assert all(path.read_bytes() == value for path, value in before.items())


def test_audit_output_budget_is_explicit_bound_and_not_a_terminal_retry(tmp_path, source):
    study = Study(tmp_path)
    review = asyncio.run(audit_pair(study, source, tmp_path / "wide-audit", max_tokens=32768))
    assert review["status"] == "DEV_AUTO_AUDITED"
    assert all(call[3]["max_tokens"] == 32768 for call in study.calls)
    assert asyncio.run(audit_pair(study, source, tmp_path / "wide-audit", max_tokens=32768)) == review
    assert len(study.calls) == 2
    with pytest.raises(ValueError, match="budget changed"):
        asyncio.run(audit_pair(study, source, tmp_path / "wide-audit", max_tokens=16384))


def test_unrelated_review_documents_cannot_admit_a_real_source_even_with_two_accepts(tmp_path, source):
    from ioabench.v5.ai_generation.development import admission, structure_vector
    from ioabench.v5.ai_generation.direct_deepseek import SCOPE
    from ioabench.v5.core.case import case_from_dict
    result = json.loads((source / "RESULT.json").read_text())
    result.update(scope=SCOPE, machine_qualified=False)
    atomic_json(source / "RESULT.json", result)
    atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
    packet = prepare_audit_packet(source)
    packet["documents"]["cases"][0]["scenario_world"] = {"unrelated": "plausible replacement"}
    study = Study(tmp_path)
    review = asyncio.run(audit_packet(study, packet, tmp_path / "swapped"))
    assert review["status"] == "DEV_AUTO_AUDITED"
    case = case_from_dict(json.loads((source / "PAIR.json").read_text())[0], allow_dynamic=True)
    with pytest.raises(ValueError, match="sealed source facts"):
        admission(source, review, structure_vector(case), audit_directory=tmp_path / "swapped")
    assert len(study.calls) == 2


def test_single_effort_is_not_two_independent_requests(tmp_path, source):
    with pytest.raises(ValueError, match="two isolated"):
        asyncio.run(audit_pair(Study(tmp_path), source, tmp_path / "audit", efforts=("high", "high")))


def test_protocol11_observations_have_run_origins_and_old_packet_is_unchanged(tmp_path, source):
    from ioabench.v5.ai_generation.development_audit import CURRENT_PROTOCOL, VERSION
    legacy = prepare_audit_packet(source)
    packet = prepare_audit_packet(source, protocol=CURRENT_PROTOCOL)
    observed = packet["documents"]["execution"]["sut_visible"]["messages"]
    assert {row["arm"] for row in observed} == {"CONTROL", "RISK"}
    assert {row["run_ordinal"] for row in observed} == set(range(6))
    assert all("case_id" in row for row in observed)
    assert "run_ordinal" not in legacy["documents"]["execution"]["sut_visible"]["messages"][0]
    assert prepare_audit_packet(source) == legacy and legacy["version"] == VERSION
    study = Study(tmp_path)
    result = asyncio.run(audit_pair(study, source, tmp_path / "v11", protocol=CURRENT_PROTOCOL, max_tokens=65536))
    assert result["status"] == "DEV_AUTO_AUDITED" and result["version"] == CURRENT_PROTOCOL
    assert all(call[3]["max_tokens"] == 65536 for call in study.calls)
    assert "/value/runs/0 is not" in study.calls[0][2][0]["content"]
    assert asyncio.run(audit_pair(study, source, tmp_path / "v11", protocol=CURRENT_PROTOCOL, max_tokens=65536)) == result
    assert len(study.calls) == 2


def test_extracted_evidence_mapping_preserves_sealed_hashes_and_rejects_escape(tmp_path, source, monkeypatch):
    import ioabench.v5.ai_generation.development_audit as module
    packet = prepare_audit_packet(source)
    packet["source_binding"]["directory"] = str(Path("X:/original-project") / source.name)
    digest = canonical_sha256(packet)
    monkeypatch.setenv("IOABENCH_EVIDENCE_ORIGINAL_ROOT", "X:/original-project")
    monkeypatch.setattr(module, "__file__", str(tmp_path / "src/ioabench/v5/ai_generation/development_audit.py"))
    module._source_check(packet["source_binding"])
    assert canonical_sha256(packet) == digest
    with pytest.raises(ValueError, match="outside the original workspace"):
        module.evidence_path("X:/outside/source")


def test_shared_router_preserves_auditor_role_usage_cost_receipts_and_no_send_resume(tmp_path, source):
    from ioabench.v5.ai_generation.direct_deepseek import DirectStudy

    class Port:
        base_url = "https://api.deepseek.com"
        def __init__(self):
            self.requests = []
        async def generate(self, profile, request):
            self.requests.append((profile, request))
            assert profile.role == request.role_metadata["role"] == "DEV_AUDITOR"
            response = await Study(tmp_path).invoke(tmp_path, "fake", request.messages,
                                                   request.parameters, role="DEV_AUDITOR")
            return response

    port = Port()
    study = DirectStudy(tmp_path, port, [{"id": "deepseek-flash"}])
    first = run(study, source, tmp_path / "audit")
    assert first["status"] == "DEV_AUTO_AUDITED"
    ledger = [json.loads(line) for line in (tmp_path / "REQUEST_LEDGER.jsonl").read_text().splitlines()]
    finished = [row for row in ledger if row["event"] == "REQUEST_FINISHED"]
    assert len(finished) == 2 and all(row["usage"] == {"prompt_tokens": 8, "completion_tokens": 9} for row in finished)
    assert all(row["cost"]["upper_cny"] > 0 and row["cost"]["actual_invoice"] == "UNKNOWN" for row in finished)
    assert run(study, source, tmp_path / "audit") == first and len(port.requests) == 2
    assert (tmp_path / "REQUEST_LEDGER.jsonl").read_text().splitlines() == [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in ledger]
