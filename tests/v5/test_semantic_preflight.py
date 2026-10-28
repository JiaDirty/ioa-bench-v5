"""Hard facts are program gates; passing them still requires semantic review."""
import asyncio
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.audit_facts import evidence_summary, facts_from_documents
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V2, audit_packet, prepare_audit_packet
from ioabench.v5.evaluation import atomic_json
from tests.v5.test_tf_audit_facts import Study12, build_source, truthful_review

CHECKS = {name: True for name in ("actions", "events", "exposure", "final_state", "monitors",
                                 "outcome", "score", "status", "all_responses_consumed")}


def source_packet(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    rows = json.loads((source / "REPLAY.json").read_text(encoding="utf-8"))
    for row in rows:
        row["checks"] = dict(CHECKS)
    atomic_json(source / "REPLAY.json", rows)
    result = json.loads((source / "RESULT.json").read_text(encoding="utf-8"))
    result["evidence_sha256"]["REPLAY.json"] = hashlib.sha256((source / "REPLAY.json").read_bytes()).hexdigest()
    atomic_json(source / "RESULT.json", result)
    atomic_json(source / "TERMINAL.json", {"result_sha256": canonical_sha256(result)})
    return prepare_audit_packet(source, protocol=PROTOCOL_V2)


class SemanticStudy(Study12):
    def _review(self, messages):
        supplied = json.loads(messages[-1]["content"])
        review = truthful_review(supplied["documents"], self.facts, **self.review_options)
        del review["fact_claims"]
        ids = {(ref["file"], ref["json_pointer"]): ref["evidence_id"] for ref in supplied["citation_catalog"]}
        review["evidence_refs"] = [{"evidence_id": ids[ref["file"], ref["json_pointer"]], "claim": ref["claim"]}
                                   for ref in review["evidence_refs"]]
        if review["verdict"] != "ACCEPT":
            review["error_codes"] = ["TASK_IMPLAUSIBLE"]
        return json.dumps(review)


class NeverStudy:
    def __init__(self, out):
        self.out, self.calls = out, []
    async def invoke(self, *args, **kwargs):
        self.calls.append(args)
        raise AssertionError("known hard failure must never reach a model")


@pytest.mark.parametrize("kind,code", [("UNPAIRED", "UNPAIRED"), ("CROSS_SUITE_PACKET", "CROSS_SUITE_PACKET"),
    ("SINGLE_ARM_EXECUTION", "SINGLE_ARM_EXECUTION"), ("MULTIPLE_INTERVENTIONS", "MULTIPLE_INTERVENTIONS"),
    ("NO_CAUSAL_EFFECT", "NO_CAUSAL_EFFECT"), ("TOOL_RECEIPT_POLLUTION", "ACTION_OBSERVATION_EVIDENCE_CONTRADICTION")])
def test_hard_failure_recomputed_without_private_expected_label(tmp_path, monkeypatch, kind, code):
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    mutate = runpy.run_path(str(scripts / "audit_citation_trial.py"))["mutated_packet"]
    base = source_packet(tmp_path)
    packet = mutate(base, kind)
    packet["hard_gate_errors"] = []
    study = NeverStudy(tmp_path)
    out = tmp_path / "audit"
    result = asyncio.run(audit_packet(study, packet, out))
    assert result["status"] == "REJECTED"
    assert code in result["hard_gate_errors"]
    assert study.calls == [] and result["reviews"] == []
    assert asyncio.run(audit_packet(study, packet, out)) == result
    from ioabench.v5.ai_generation.audit_citations import verify_registered_result
    assert verify_registered_result(out)["raw_reviews_reconstructed"] == 0


@pytest.mark.parametrize("verdict,status", [("ACCEPT", "DEV_AUTO_AUDITED"), ("REJECT", "REJECTED"),
                                           ("UNCERTAIN", "QUARANTINED")])
def test_hard_pass_does_not_substitute_for_two_semantic_decisions(tmp_path, verdict, status):
    packet = source_packet(tmp_path)
    study = SemanticStudy(tmp_path, packet["audit_facts"], verdict=verdict)
    study.audit_output_mode = "json_schema"
    result = asyncio.run(audit_packet(study, packet, tmp_path / "review"))
    assert result["status"] == status, result
    assert len(study.calls) == 2
    assert all(not row["validation_errors"] for row in result["reviews"])
    assert all("fact_claims" not in row["review"] for row in result["reviews"])
    sent = json.loads(study.calls[0][1][-1]["content"])
    assert "program_verified_facts" in sent and "required_accept_fact_keys" not in sent
    from ioabench.v5.ai_generation.audit_citations import verify_registered_result
    assert verify_registered_result(tmp_path / "review")["raw_reviews_reconstructed"] == 2


def test_incomplete_replay_cannot_pass_on_remaining_true_flags(tmp_path):
    packet = source_packet(tmp_path)
    del packet["documents"]["replay"][0]["checks"]["events"]
    study = NeverStudy(tmp_path)
    result = asyncio.run(audit_packet(study, packet, tmp_path / "missing-check"))
    assert "STRICT_REPLAY_CHECKS_INCOMPLETE" in result["hard_gate_errors"]
    assert study.calls == []


def test_unbound_semantic_document_cannot_enter_review_as_sealed_evidence(tmp_path):
    packet = source_packet(tmp_path)
    for case in packet["documents"]["cases"]:
        case["scenario_world"]["brief"] = "A different task not present in the source bytes."
    study = NeverStudy(tmp_path)
    result = asyncio.run(audit_packet(study, packet, tmp_path / "unbound"))
    assert "PACKET_SOURCE_MISMATCH" in result["hard_gate_errors"]
    assert study.calls == []
