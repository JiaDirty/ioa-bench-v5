"""Program-owned locations for review protocol 1.3; no inferred review content."""
from __future__ import annotations

from copy import deepcopy
import json

EVIDENCE_GROUPS = ('cases', 'execution', 'history', 'replay', 'additional')


def citation_catalog(documents):
    locations = set()
    observation_ids = {}
    for wrapper in documents.values():
        name, value = wrapper["file"], wrapper["value"]
        locations.add((name, ""))
        if isinstance(value, dict):
            for key in value:
                locations.add((name, "/" + key.replace("~", "~0").replace("/", "~1")))
        elif isinstance(value, list):
            for index, row in enumerate(value):
                locations.add((name, f"/{index}"))
                if isinstance(row, dict):
                    for key in row:
                        locations.add((name, f"/{index}/" + key.replace("~", "~0").replace("/", "~1")))
    execution = documents["execution"]
    for index, run in enumerate(execution["value"]["runs"]):
        locations.add((execution["file"], f"/runs/{index}"))
        for key in ("actions", "events", "final_state"):
            locations.add((execution["file"], f"/runs/{index}/{key}"))
        for position, _ in enumerate(run["actions"]):
            locations.add((execution["file"], f"/runs/{index}/actions/{position}"))
        if 'evaluation' in run:
            locations.add((execution['file'], f'/runs/{index}/evaluation'))
            for key in run['evaluation']:
                locations.add((execution['file'], f'/runs/{index}/evaluation/{key}'))
    for index, run in enumerate(execution['value'].get('tool_observation_ledger', [])):
        locations.add((execution['file'], f'/tool_observation_ledger/{index}'))
        for position, observation in enumerate(run['observations']):
            location = (execution['file'], f'/tool_observation_ledger/{index}/observations/{position}')
            locations.add(location)
            if 'evidence_id' in observation:
                observation_ids[location] = observation['evidence_id']
    hashes = {wrapper["file"]: wrapper["sha256"] for wrapper in documents.values()}
    return [{"evidence_id": observation_ids.get((name, pointer), f"E{index:03}"), "file": name, "json_pointer": pointer,
             "sha256": hashes[name]} for index, (name, pointer) in enumerate(sorted(locations))]


def review_response_schema(catalog, fact_keys, error_codes, *, include_fact_claims=True, grouped_references=False):
    """Constrain the existing review shape, never its verdict or fact values."""
    text = {"type": "string", "minLength": 1}
    evidence_id = {"type": "string", "enum": [row["evidence_id"] for row in catalog]}
    json_value = {"anyOf": [{"type": kind} for kind in ("boolean", "integer", "string", "null")] + [
        {"type": "array", "items": {"type": "string"}}]}
    properties = {
        "verdict": {"type": "string", "enum": ["ACCEPT", "REJECT", "UNCERTAIN"]},
        "error_codes": {"type": "array", "items": {"type": "string", "enum": sorted(error_codes)}},
        "evidence_refs": {"type": "array", "minItems": 1, "items": {
            "type": "object", "properties": {"evidence_id": evidence_id, "claim": text},
            "required": ["evidence_id", "claim"], "additionalProperties": False}},
        "fact_claims": {"type": "array", "minItems": 1, "items": {
            "type": "object", "properties": {
                "fact_key": {"type": "string", "enum": sorted(set(fact_keys) - {"version"})},
                "value": json_value, "evidence_id": evidence_id},
            "required": ["fact_key", "value", "evidence_id"], "additionalProperties": False}}}
    properties.update({key: text for key in ("causal_mechanism", "control_risk_delta", "novelty_claim", "difficulty_rationale")})
    properties.update({key: {"type": "array", "minItems": 1, "items": text}
                       for key in ("reuse_constraints", "disconfirming_checks")})
    if not include_fact_claims:
        del properties["fact_claims"]
    if grouped_references:
        groups = {name: {'type': 'array', 'minItems': 0 if name == 'additional' else 1,
            'items': {'type': 'object', 'properties': {
                'evidence_id': {'type': 'string', 'enum': [r['evidence_id'] for r in catalog
                    if name == 'additional' or r['file'] == f'inputs/{name}.json']}, 'claim': text},
                'required': ['evidence_id', 'claim'], 'additionalProperties': False}}
            for name in EVIDENCE_GROUPS}
        properties['evidence_refs'] = {'type': 'object', 'properties': groups,
            'required': list(groups), 'additionalProperties': False}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def bind_citations(review, catalog, *, include_fact_references=False, semantic_only=False, grouped_references=False):
    """Expand only registered IDs; preserve every model verdict, value and claim."""
    if not isinstance(review, dict):
        raise ValueError("citation review must be an object")
    bound = deepcopy(review)
    if semantic_only:
        if "fact_claims" in bound:
            raise ValueError("deterministic facts belong to program preflight, not model output")
        bound["fact_claims"] = []
    registered = {row["evidence_id"]: row for row in catalog}
    if grouped_references:
        groups = bound.get('evidence_refs')
        if not isinstance(groups, dict) or set(groups) != set(EVIDENCE_GROUPS):
            raise ValueError('all grouped evidence fields required')
        refs = []
        for name in EVIDENCE_GROUPS:
            values = groups[name]
            if not isinstance(values, list) or (name != 'additional' and not values):
                raise ValueError('required evidence group is empty')
            for ref in values:
                if not isinstance(ref, dict) or set(ref) != {'evidence_id', 'claim'}:
                    raise ValueError('citation reference fields invalid')
                entry = registered.get(ref['evidence_id'])
                if entry is None or (name != 'additional' and entry['file'] != f'inputs/{name}.json'):
                    raise ValueError('citation does not belong to its evidence group')
                refs.append(ref)
        bound['evidence_refs'] = refs
    cited = set()
    refs = bound.get("evidence_refs")
    claims = bound.get("fact_claims")
    if not isinstance(refs, list) or not isinstance(claims, list):
        raise ValueError("citation and fact_claim arrays required")
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"evidence_id", "claim"}:
            raise ValueError("citation reference fields invalid")
        evidence_id = ref.pop("evidence_id")
        if not isinstance(evidence_id, str) or evidence_id not in registered:
            raise ValueError("unknown citation ID")
        cited.add(evidence_id)
        ref.update({key: value for key, value in registered[evidence_id].items() if key != "evidence_id"})
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {"evidence_id", "fact_key", "value"}:
            raise ValueError("citation fact claim fields invalid")
        evidence_id = claim.pop("evidence_id")
        if not isinstance(evidence_id, str) or evidence_id not in registered:
            raise ValueError("unknown fact citation ID")
        if evidence_id not in cited:
            if not include_fact_references:
                raise ValueError("fact claim citation must be cited in evidence_refs")
            source = registered[evidence_id]
            bound["evidence_refs"].append({key: value for key, value in source.items() if key != "evidence_id"} | {
                "claim": claim["fact_key"] + " = " + json.dumps(claim["value"], ensure_ascii=False, sort_keys=True)})
            cited.add(evidence_id)
        source = registered[evidence_id]
        claim.update(evidence_file=source["file"], json_pointer=source["json_pointer"])
    if semantic_only:
        del bound["fact_claims"]
    return bound


def verify_registered_result(directory):
    """Rebuild normalized reviews from retained raw responses and registered bytes."""
    from pathlib import Path
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation.audit_facts import facts_from_documents
    from ioabench.v5.ai_generation.development_audit import (
        ERROR_CODES, PROTOCOL_V13, PROTOCOL_V14, GROUPED_CITATION_PROTOCOLS, SEMANTIC_PROTOCOLS, _read, _saved_result, _sha, evidence_path, prepare_audit_packet, validate_review)
    from ioabench.v5.ai_generation.factory import decode_json

    directory = Path(directory)
    packet = _read(directory / "AUDIT_PACKET.json")
    if packet["version"] not in {PROTOCOL_V13, PROTOCOL_V14, *SEMANTIC_PROTOCOLS}:
        raise ValueError("registered citation verification requires protocol 1.3, 1.4, 2.0 or 2.1")
    result = _saved_result(directory, packet)
    bindings = _read(directory / "DOCUMENT_BINDINGS.json")
    wrappers = {}
    for name, value in packet["documents"].items():
        relative = "inputs/" + name + ".json"
        if _read(directory / relative) != value or _sha(directory / relative) != bindings[relative]:
            raise ValueError("registered input differs from the packet")
        wrappers[name] = {"file": relative, "sha256": bindings[relative], "value": value}
    catalog = citation_catalog(wrappers)
    if catalog != _read(directory / "CITATION_CATALOG.json"):
        raise ValueError("citation catalog differs from actual input locations")
    output_path = directory / "AUDIT_OUTPUT_CONTRACT.json"
    output_contract = _read(output_path) if output_path.exists() else None
    if output_contract is not None:
        expected = {"type": "json_schema", "json_schema": {"name": "ioabench_registered_review", "strict": True,
            "schema": review_response_schema(catalog, packet["audit_facts"], ERROR_CODES,
                                             include_fact_claims=packet["version"] not in SEMANTIC_PROTOCOLS,
                                             grouped_references=packet["version"] in GROUPED_CITATION_PROTOCOLS)}}
        if packet["version"] not in {PROTOCOL_V14, *SEMANTIC_PROTOCOLS} or expected != output_contract:
            raise ValueError("native output contract differs from registered review requirements")
    settings = directory / "AUDIT_SETTINGS.json"
    identity = {"packet": packet, "max_tokens": _read(settings)["max_tokens"] if settings.exists() else 16384}
    if output_contract is not None:
        identity["output_contract"] = output_contract
    facts = facts_from_documents(packet["documents"], base=packet["audit_facts"])
    facts["oracle_leakage_present"] = packet["audit_facts"]["oracle_leakage_present"]
    if packet["version"] in SEMANTIC_PROTOCOLS:
        from ioabench.v5.ai_generation.audit_preflight import preflight
        expected = preflight(packet, facts)
        if expected != _read(directory / "PROGRAM_PREFLIGHT.json") or result["hard_gate_errors"] != expected["errors"]:
            raise ValueError("semantic audit changed its deterministic preflight")
        if expected["status"] != "PASS" and (result["reviews"] or result["status"] != "REJECTED"):
            raise ValueError("hard-failed packet reached semantic review or admission")
    verified = 0
    for row in result["reviews"]:
        if row["request_id"] != "audit-" + row["effort"] + "-" + canonical_sha256(identity)[:16]:
            raise ValueError("registered request ID differs from its packet and output contract")
        if "review" not in row:
            continue
        response = _read(directory / ("AUDIT_" + row["effort"] + "_RESPONSE.json"))
        bound = bind_citations(decode_json(response["text"]), catalog,
                               include_fact_references=packet["version"] == PROTOCOL_V14,
                               semantic_only=packet["version"] in SEMANTIC_PROTOCOLS,
                               grouped_references=packet["version"] in GROUPED_CITATION_PROTOCOLS)
        if bound != row["review"] or response["usage"] != row["usage"]:
            raise ValueError("normalized review differs from the raw model response")
        errors = validate_review(bound, directory, bindings, protocol=packet["version"], facts=facts)
        if not set(errors) <= set(row["validation_errors"]):
            raise ValueError("registered audit omitted fact or evidence errors")
        verified += 1
    if result["status"] == "DEV_AUTO_AUDITED":
        source_packet = prepare_audit_packet(evidence_path(packet["source_binding"]["directory"]),
                                            protocol=packet["version"])
        if canonical_sha256(source_packet) != canonical_sha256(packet):
            raise ValueError("accepted registered packet differs from its sealed source")
        if (verified != 2 or packet["hard_gate_errors"] or any(
                row["validation_errors"] or row["review"]["verdict"] != "ACCEPT"
                for row in result["reviews"])):
            raise ValueError("registered admission lacks two valid accepts")
    return {"status": "PASS", "audit_status": result["status"], "raw_reviews_reconstructed": verified}
