"""Registered review citations bind real evidence without model-written hashes."""
import asyncio
import json

import pytest

from ioabench.v5.ai_generation.audit_citations import citation_catalog, bind_citations
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V13, PROTOCOL_V14, audit_packet, prepare_audit_packet
from tests.v5.test_tf_audit_facts import Study12, build_source, truthful_review


class CitationStudy(Study12):
    def _review(self, messages):
        supplied = json.loads(messages[-1]["content"])
        catalog = supplied["citation_catalog"]
        by_location = {(ref["file"], ref["json_pointer"]): ref["evidence_id"] for ref in catalog}
        review = truthful_review(supplied["documents"], self.facts, **self.review_options)
        review["evidence_refs"] = [{"evidence_id": by_location[ref["file"], ref["json_pointer"]],
                                   "claim": ref["claim"]} for ref in review["evidence_refs"]]
        review["fact_claims"] = [{"fact_key": claim["fact_key"], "value": claim["value"],
                                 "evidence_id": by_location[claim["evidence_file"], claim["json_pointer"]]}
                                for claim in review["fact_claims"]]
        if self.mode == "unknown-citation":
            review["evidence_refs"][0]["evidence_id"] = "invented"
        if self.mode == "fact-citations":
            review["evidence_refs"] = review["evidence_refs"][:1]
        return json.dumps(review)


def test_catalog_is_reproducible_and_resolves_exact_actual_action(tmp_path):
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V13)
    documents = {name: {"file": "inputs/" + name + ".json", "sha256": name + "-hash", "value": value}
                 for name, value in packet["documents"].items()}
    catalog = citation_catalog(documents)
    assert catalog == citation_catalog(documents)
    row = next(ref for ref in catalog if ref["file"] == "inputs/execution.json"
               and ref["json_pointer"] == "/runs/1/actions/0")
    raw = {"evidence_refs": [{"evidence_id": row["evidence_id"], "claim": "Actual action."}],
           "fact_claims": [{"fact_key": "reference_action_count", "value": 6,
                            "evidence_id": row["evidence_id"]}]}
    bound = bind_citations(raw, catalog)
    assert bound["evidence_refs"] == [{"file": "inputs/execution.json",
        "sha256": "execution-hash", "json_pointer": "/runs/1/actions/0", "claim": "Actual action."}]
    assert bound["fact_claims"][0]["value"] == 6
    assert "evidence_id" in raw["evidence_refs"][0]
    with pytest.raises(ValueError, match="citation"):
        bind_citations({**raw, "evidence_refs": [{"evidence_id": "invented", "claim": "x"}]}, catalog)


@pytest.mark.parametrize("mode,overrides,expected", [
    ("truthful", None, "DEV_AUTO_AUDITED"),
    ("truthful", {"replay_rows": 999}, "QUARANTINED"),
    ("unknown-citation", None, "QUARANTINED")])
def test_registered_audit_keeps_raw_response_truth_checks_and_terminal_reentry(
        tmp_path, mode, overrides, expected):
    source, _ = build_source(tmp_path, "T321")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V13)
    study = CitationStudy(tmp_path, packet["audit_facts"], mode=mode, overrides=overrides)
    directory = tmp_path / "audit"
    result = asyncio.run(audit_packet(study, packet, directory))
    assert result["status"] == expected
    if overrides:
        assert all("CLAIM_FACT_CONTRADICTION:replay_rows" in row["validation_errors"]
                   for row in result["reviews"])
    if mode == "unknown-citation":
        assert all("AUDIT_FORMAT_INVALID" in row["validation_errors"] for row in result["reviews"])
    else:
        response = json.loads((directory / "AUDIT_high_RESPONSE.json").read_text(encoding="utf-8"))
        assert "sha256" not in json.loads(response["text"])["evidence_refs"][0]
        assert "sha256" in result["reviews"][0]["review"]["evidence_refs"][0]
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    assert asyncio.run(audit_packet(study, packet, directory)) == result
    assert len(study.calls) == 2
    assert before == {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    if mode != "unknown-citation":
        from ioabench.v5.ai_generation.audit_citations import verify_registered_result
        assert verify_registered_result(directory)["raw_reviews_reconstructed"] == 2


def test_registered_claim_must_cite_an_actual_evidence_ref():
    catalog = [{"evidence_id": "E0", "file": "inputs/cases.json", "json_pointer": "", "sha256": "x"},
               {"evidence_id": "E1", "file": "inputs/execution.json", "json_pointer": "", "sha256": "y"}]
    with pytest.raises(ValueError, match="cited"):
        bind_citations({"evidence_refs": [{"evidence_id": "E0", "claim": "pair"}],
                        "fact_claims": [{"evidence_id": "E1", "fact_key": "arms", "value": []}]}, catalog)


@pytest.mark.parametrize("overrides,expected", [(None, "DEV_AUTO_AUDITED"),
                                              ({"replay_rows": 999}, "QUARANTINED")])
def test_v14_fact_citation_is_sufficient_and_keeps_asserted_value(tmp_path, overrides, expected):
    from ioabench.v5.ai_generation.audit_citations import verify_registered_result
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V14)
    study = CitationStudy(tmp_path, packet["audit_facts"], mode="fact-citations", overrides=overrides)
    directory = tmp_path / "v14"
    result = asyncio.run(audit_packet(study, packet, directory))
    assert result["status"] == expected
    assert verify_registered_result(directory)["raw_reviews_reconstructed"] == 2
    raw = json.loads(json.loads((directory / "AUDIT_high_RESPONSE.json").read_text(encoding="utf-8"))["text"])
    assert len(raw["evidence_refs"]) == 1
    assert len(result["reviews"][0]["review"]["evidence_refs"]) > 1
    assert [(c["fact_key"], c["value"]) for c in raw["fact_claims"]] == [
        (c["fact_key"], c["value"]) for c in result["reviews"][0]["review"]["fact_claims"]]
    assert "need not be repeated" in study.calls[0][1][0]["content"]
    if overrides:
        assert all("CLAIM_FACT_CONTRADICTION:replay_rows" in r["validation_errors"] for r in result["reviews"])


def test_native_schema_binds_fresh_requests_and_rejects_empty_constraints(tmp_path):
    from jsonschema import Draft202012Validator
    from ioabench.v5.ai_generation.audit_citations import verify_registered_result
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V14)
    original = CitationStudy(tmp_path, packet["audit_facts"], mode="fact-citations")
    asyncio.run(audit_packet(original, packet, tmp_path / "json-object"))
    strict = CitationStudy(tmp_path, packet["audit_facts"], mode="fact-citations")
    strict.audit_output_mode = "json_schema"
    result = asyncio.run(audit_packet(strict, packet, tmp_path / "strict"))
    assert result["status"] == "DEV_AUTO_AUDITED"
    assert set(c[0] for c in original.calls).isdisjoint(c[0] for c in strict.calls)
    assert verify_registered_result(tmp_path / "strict")["raw_reviews_reconstructed"] == 2
    contract = json.loads((tmp_path / "strict/AUDIT_OUTPUT_CONTRACT.json").read_text(encoding="utf-8"))
    raw = json.loads(json.loads((tmp_path / "strict/AUDIT_high_RESPONSE.json").read_text(encoding="utf-8"))["text"])
    validator = Draft202012Validator(contract["json_schema"]["schema"])
    assert not list(validator.iter_errors(raw))
    raw["reuse_constraints"] = []
    assert any(list(e.path) == ["reuse_constraints"] for e in validator.iter_errors(raw))


def test_gateway_schema_degradation_does_not_qualify_a_review(tmp_path):
    from dataclasses import replace
    class DegradedStudy(CitationStudy):
        async def invoke(self, *args, **kwargs):
            response = await super().invoke(*args, **kwargs)
            return replace(response, provider_metadata={"model": "deepseek-flash", "transport_metadata": {
                "x-structured-output-degraded": "json_schema_unsupported"}})
    source, _ = build_source(tmp_path, "T321")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V14)
    study = DegradedStudy(tmp_path, packet["audit_facts"])
    study.audit_output_mode = "json_schema"
    result = asyncio.run(audit_packet(study, packet, tmp_path / "degraded"))
    assert result["status"] == "QUARANTINED"
    assert all("STRUCTURED_OUTPUT_DEGRADED" in row["validation_errors"] for row in result["reviews"])


def test_schema_accepted_by_provider_is_checked_against_actual_response(tmp_path):
    class SchemaViolatingStudy(CitationStudy):
        def _review(self, messages):
            review = json.loads(super()._review(messages))
            review["difficulty_rationale"] = ""
            return json.dumps(review)
    source, _ = build_source(tmp_path, "T331")
    packet = prepare_audit_packet(source, protocol=PROTOCOL_V14)
    study = SchemaViolatingStudy(tmp_path, packet["audit_facts"])
    study.audit_output_mode = "json_schema"
    result = asyncio.run(audit_packet(study, packet, tmp_path / "ignored-schema"))
    assert result["status"] == "QUARANTINED"
    assert all("REVIEW_OUTPUT_SCHEMA_VIOLATION" in row["validation_errors"] for row in result["reviews"])
    assert all(any(error["json_pointer"] == "/difficulty_rationale" for error in row["output_schema_errors"])
               for row in result["reviews"])


@pytest.mark.parametrize("kind,expected", [
    ("MULTIPLE_INTERVENTIONS", "MULTIPLE_INTERVENTIONS"),
    ("NO_CAUSAL_EFFECT", "NO_CAUSAL_EFFECT"),
    ("SINGLE_ARM_EXECUTION", "SINGLE_ARM_EXECUTION"),
    ("TOOL_RECEIPT_POLLUTION", "ACTION_OBSERVATION_EVIDENCE_CONTRADICTION"),
    ("CROSS_SUITE_PACKET", "CROSS_SUITE_PACKET"),
    ("UNPAIRED", "UNPAIRED")])
def test_frozen_calibration_mutations_are_actual_blocking_evidence(tmp_path, monkeypatch, kind, expected):
    from pathlib import Path
    import runpy
    from ioabench.v5.ai_generation.audit_facts import assertion_evidence_consistency
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "audit_citation_trial.py"))
    source, _ = build_source(tmp_path, "T331")
    base = prepare_audit_packet(source, protocol=PROTOCOL_V13)
    before = json.dumps(base, sort_keys=True)
    mutated = trial["mutated_packet"](base, kind)
    assert json.dumps(base, sort_keys=True) == before
    from ioabench.v5.ai_generation.audit_facts import evidence_summary
    summary = evidence_summary(mutated["documents"])
    assert {key: mutated["documents"]["facts_summary"][key] for key in summary} == summary
    facts = mutated["audit_facts"]
    errors = assertion_evidence_consistency({"verdict": "ACCEPT", "evidence_refs": [],
        "fact_claims": [{"fact_key": "arms", "value": facts["arms"], "evidence_file": "x", "json_pointer": ""}]}, facts)
    assert expected in errors
