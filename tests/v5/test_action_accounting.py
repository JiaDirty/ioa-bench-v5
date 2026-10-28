"""Tool call totals, distinct executions and protocol2.2 source provenance."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ioabench.v5.ai_generation import audit_facts, development_audit as audit
from tests.v5.test_semantic_preflight import NeverStudy, SemanticStudy, source_packet


def documents():
    return {'execution': {'runs': [
        {'run_ordinal': 0, 'arm': 'CONTROL', 'case_id': 'c', 'actions': [
            {'seq': 1, 'tool': 'request_reconstruction', 'status': 'ok'},
            {'seq': 2, 'tool': 'request_reconstruction', 'status': 'error'},
            {'seq': 3, 'tool': 'lookup_document', 'status': 'ok'}]},
        {'run_ordinal': 1, 'arm': 'RISK', 'case_id': 'r', 'actions': [
            {'seq': 1, 'tool': 'lookup_document', 'status': 'ok'},
            {'seq': 2, 'tool': 'lookup_document', 'status': 'ok'}]},
        {'run_ordinal': 2, 'arm': 'RISK', 'case_id': 'r', 'actions': []}]}}


def test_success_failure_repetition_and_distinct_runs_stay_separate():
    data = documents()
    before = deepcopy(data)
    counts = audit_facts.action_accounting(data)
    assert data == before
    assert counts['totals_by_tool'] == {
        'lookup_document': {'successful_calls': 3, 'failed_calls': 0, 'runs_with_successful_calls': 2},
        'request_reconstruction': {'successful_calls': 1, 'failed_calls': 1, 'runs_with_successful_calls': 1}}
    assert counts['runs'][0]['tools']['request_reconstruction'] == {
        'successful_sequences': [1], 'failed_sequences': [2]}
    assert counts['runs'][2]['tools'] == {}
    assert audit_facts.action_accounting({'execution': {'runs': []}})['totals_by_tool'] == {}
    compact = {'execution': audit_facts.compact_execution(data['execution'])}
    assert audit_facts.action_accounting(compact) == counts


@pytest.mark.parametrize('mutation', ['total', 'per_run', 'missing'])
def test_incorrect_action_table_stops_before_auditor_call(tmp_path, mutation):
    original = source_packet(tmp_path)
    packet = audit.prepare_audit_packet(Path(original['source_binding']['directory']), protocol=audit.PROTOCOL_V22)
    counts = packet['documents']['facts_summary']['action_accounting']
    if mutation == 'total':
        next(iter(counts['totals_by_tool'].values()))['successful_calls'] += 1
    elif mutation == 'per_run':
        counts['runs'][0]['tools'].clear()
    else:
        del packet['documents']['facts_summary']['action_accounting']
    study = NeverStudy(tmp_path)
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == 'REJECTED' and study.calls == []
    assert 'ACTION_ACCOUNTING_CONTRADICTION' in result['hard_gate_errors']


def test_provenance_and_counts_reach_native_schema_review_without_legacy_changes(tmp_path):
    original = source_packet(tmp_path)
    directory = Path(original['source_binding']['directory'])
    legacy = audit.prepare_audit_packet(directory, protocol=audit.PROTOCOL_V21)
    packet = audit.prepare_audit_packet(directory, protocol=audit.PROTOCOL_V22)
    assert 'action_accounting' not in legacy['documents']['facts_summary']
    assert 'origin' not in legacy['documents']['execution']
    assert packet['documents']['execution']['origin']['evidence_classes'] == ['ENGINEERING_REFERENCE']
    assert packet['documents']['execution']['origin']['model_ids'] == ['reference-policy']
    study = SemanticStudy(tmp_path, packet['audit_facts'], verdict='REJECT')
    study.audit_output_mode = 'json_schema'
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == 'REJECTED' and len(study.calls) == 2
    sent = json.loads(study.calls[0][1][-1]['content'])
    assert 'action_accounting' in sent['documents']['facts_summary']['value']
    assert 'Scripted reference policies' in study.calls[0][1][0]['content']
    from ioabench.v5.ai_generation.audit_citations import verify_registered_result
    assert verify_registered_result(tmp_path / 'review')['raw_reviews_reconstructed'] == 2
