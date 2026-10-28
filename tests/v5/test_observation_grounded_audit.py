"""Protocol2.3 preserves observation scope and requires explicit document coverage."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ioabench.v5.ai_generation import development_audit as audit
from ioabench.v5.ai_generation.audit_facts import tool_observation_ledger
from ioabench.v5.ai_generation.audit_citations import (
    EVIDENCE_GROUPS, bind_citations, review_response_schema, verify_registered_result)
from ioabench.v5.core.trace_integrity import inspect_tool_observations
from tests.v5.test_semantic_preflight import NeverStudy, SemanticStudy, source_packet


def trace_with_reused_call_ids():
    def record(actor, turn, messages, calls):
        return {'agent_id': actor, 'turn': turn, 'request': {'messages': messages},
                'response': {'tool_calls': [{'id': 'dup', 'function': {'name': name}} for name in calls]}}
    def seen(value):
        return [{'role': 'assistant'}, {'role': 'tool', 'tool_call_id': 'dup', 'content': json.dumps(value)}]
    actions = [{'seq': seq, 'actor': actor, 'turn': turn, 'tool': tool, 'arguments': {}, 'status': 'ok', 'result': result}
        for seq, actor, turn, tool, result in [
            (1, 'a', 1, 'lookup', {'found': False}), (2, 'b', 1, 'lookup', {'found': True}),
            (3, 'a', 2, 'execute', {'done': True})]]
    return {'actions': actions, 'records': [record('a', 1, [], ['lookup']), record('b', 1, [], ['lookup']),
        record('a', 2, seen({'found': False}), ['execute']), record('b', 2, seen({'found': True}), [])]}


def test_reused_call_ids_and_terminal_receipts_do_not_invent_observation():
    trace = trace_with_reused_call_ids()
    integrity = inspect_tool_observations(trace)
    assert integrity['compared'] == 2 and integrity['not_observed_in_a_later_request'] == 1
    assert not integrity['alignment_errors'] and not integrity['mismatches']
    rows = [{'arm': 'RISK', 'case_id': 'r', 'trace': trace}, {'arm': 'RISK', 'case_id': 'r', 'trace': trace}]
    before = deepcopy(rows)
    ledger = tool_observation_ledger(rows)
    assert rows == before
    assert [r['run_ordinal'] for r in ledger] == [0, 1]
    assert [r['observed_result'] for r in ledger[0]['observations']] == [{'found': False}, {'found': True}, None]
    terminal = ledger[0]['observations'][2]
    assert terminal['recorded_result'] == {'done': True}
    assert not terminal['observed_in_later_request'] and terminal['source_observation_pointer'] is None
    assert ledger[1]['observations'][0]['source_observation_pointer'].startswith('/1/trace/records/2/')


class GroupedStudy(SemanticStudy):
    def _review(self, messages):
        review = json.loads(super()._review(messages))
        supplied = json.loads(messages[-1]['content'])
        files = {row['evidence_id']: row['file'] for row in supplied['citation_catalog']}
        groups = {key: [] for key in EVIDENCE_GROUPS}
        for ref in review['evidence_refs']:
            name = files[ref['evidence_id']].removeprefix('inputs/').removesuffix('.json')
            groups[name if name in groups else 'additional'].append(ref)
        review['evidence_refs'] = groups
        return json.dumps(review)


@pytest.mark.parametrize('verdict,status', [('ACCEPT', 'DEV_AUTO_AUDITED'), ('REJECT', 'REJECTED'), ('UNCERTAIN', 'QUARANTINED')])
def test_grouped_output_is_model_authored_and_reconstructable(tmp_path, verdict, status):
    old = source_packet(tmp_path)
    directory = Path(old['source_binding']['directory'])
    legacy = audit.prepare_audit_packet(directory, protocol=audit.PROTOCOL_V22)
    packet = audit.prepare_audit_packet(directory, protocol=audit.PROTOCOL_V23)
    assert 'tool_observation_ledger' not in legacy['documents']['execution']
    assert packet['documents']['execution']['tool_observation_ledger']
    study = GroupedStudy(tmp_path, packet['audit_facts'], verdict=verdict)
    study.audit_output_mode = 'json_schema'
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == status and len(study.calls) == 2
    assert all(not r['validation_errors'] and not r['output_schema_errors'] for r in result['reviews'])
    supplied = json.loads(study.calls[0][1][-1]['content'])
    assert any('/tool_observation_ledger/0/observations/0' == row['json_pointer'] for row in supplied['citation_catalog'])
    system = study.calls[0][1][0]['content']
    assert 'final world has that state' in system and 'evidence_refs is an object' in system
    assert 'evidence_refs is a nonempty array' not in system
    assert verify_registered_result(tmp_path / 'review')['raw_reviews_reconstructed'] == 2
    before = len(study.calls)
    assert asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review')) == result
    assert len(study.calls) == before


def test_missing_replay_and_wrong_group_are_not_silently_filled():
    catalog = [{'evidence_id': str(i), 'file': f'inputs/{name}.json', 'json_pointer': '', 'sha256': name}
               for i, name in enumerate(EVIDENCE_GROUPS[:-1])]
    refs = {name: [{'evidence_id': str(i), 'claim': name}] for i, name in enumerate(EVIDENCE_GROUPS[:-1])}
    refs['additional'] = []
    schema = review_response_schema(catalog, [], audit.ERROR_CODES, include_fact_claims=False, grouped_references=True)
    validator = Draft202012Validator(schema['properties']['evidence_refs'])
    assert not list(validator.iter_errors(refs))
    bad = deepcopy(refs)
    bad['replay'] = []
    assert list(validator.iter_errors(bad))
    with pytest.raises(ValueError, match='group is empty'):
        bind_citations({'evidence_refs': bad}, catalog, semantic_only=True, grouped_references=True)
    bad = deepcopy(refs)
    bad['replay'] = deepcopy(refs['history'])
    assert list(validator.iter_errors(bad))
    with pytest.raises(ValueError, match='does not belong'):
        bind_citations({'evidence_refs': bad}, catalog, semantic_only=True, grouped_references=True)
    bound = bind_citations({'evidence_refs': refs}, catalog, semantic_only=True, grouped_references=True)
    assert len(bound['evidence_refs']) == 4 and refs['additional'] == []


def test_changed_observation_ledger_cannot_reach_the_auditor(tmp_path):
    original = source_packet(tmp_path)
    packet = audit.prepare_audit_packet(Path(original['source_binding']['directory']), protocol=audit.PROTOCOL_V23)
    receipt = packet['documents']['execution']['tool_observation_ledger'][0]['observations'][0]
    receipt['observed_result'] = {'invented': True}
    study = NeverStudy(tmp_path)
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == 'REJECTED' and study.calls == []
    assert 'PACKET_SOURCE_MISMATCH' in result['hard_gate_errors']
