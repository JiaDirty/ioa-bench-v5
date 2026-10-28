"""Per-run business-call accounting is computed from actions and declared tools."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.v5.test_semantic_preflight import NeverStudy, SemanticStudy, source_packet
from ioabench.v5.ai_generation import audit_facts, development_audit as audit


def documents():
    return {'cases': [{'metadata': {'case_id': 'control'}, 'scenario_world': {'business_binding': {
        'plan': [{'stage_id': 's1', 'tool': 'lookup_stock'}, {'stage_id': 's2', 'tool': 'verify_lot'}]}}}],
        'execution': {'runs': [
            {'run_ordinal': 0, 'arm': 'CONTROL', 'case_id': 'control', 'actions': [
                {'seq': 1, 'tool': 'lookup_stock', 'status': 'ok'},
                {'seq': 2, 'tool': 'verify_lot', 'status': 'error'},
                {'seq': 3, 'tool': 'route_job', 'status': 'ok', 'result': {'stage_id': 's1'}}]},
            {'run_ordinal': 1, 'arm': 'CONTROL', 'case_id': 'control', 'actions': [
                {'seq': 1, 'tool': 'route_job', 'status': 'ok'}]},
            {'run_ordinal': 2, 'arm': 'CONTROL', 'case_id': 'control', 'actions': [
                {'seq': 1, 'tool': 'lookup_stock', 'status': 'ok'},
                {'seq': 2, 'tool': 'lookup_stock', 'status': 'ok'},
                {'seq': 3, 'tool': 'verify_lot', 'status': 'ok'}]}]}}


def test_counts_successful_declared_tool_calls_without_combining_runs():
    data = documents()
    before = deepcopy(data)
    result = audit_facts.execution_accounting(data)
    assert data == before
    assert [r['successful_business_tool_calls'] for r in result['runs']] == [1, 0, 3]
    assert [r['business_action_sequences'] for r in result['runs']] == [[1], [], [1, 2, 3]]
    assert result['totals'] == {'recorded_actions': 7, 'successful_actions': 6,
        'successful_business_tool_calls': 4, 'runs_with_business_tool_calls': 2, 'execution_runs': 3}
    assert result['runs'][0]['execution_json_pointer'] == '/runs/0'
    assert result['runs'][0]['business_plan_json_pointer'] == '/0/scenario_world/business_binding/plan'


def test_missing_business_instrumentation_is_unknown_instead_of_zero():
    data = documents()
    del data['cases'][0]['scenario_world']['business_binding']
    result = audit_facts.execution_accounting(data)
    assert result['totals']['successful_business_tool_calls'] is None
    assert result['totals']['runs_with_business_tool_calls'] is None
    assert all(r['successful_business_tool_calls'] is None for r in result['runs'])


def test_compaction_cannot_change_tool_call_accounting():
    data = documents()
    expected = audit_facts.execution_accounting(data)
    data['execution'] = audit_facts.compact_execution(data['execution'])
    assert audit_facts.execution_accounting(data) == expected


@pytest.mark.parametrize('mutation', ['total', 'per_run', 'omit'])
def test_wrong_or_missing_accounting_stops_before_any_model_request(tmp_path, mutation):
    original = source_packet(tmp_path)
    packet = audit.prepare_audit_packet(Path(original['source_binding']['directory']), protocol=audit.PROTOCOL_V21)
    accounting = packet['documents']['facts_summary']['execution_accounting']
    if mutation == 'total':
        accounting['totals']['recorded_actions'] += 1
    elif mutation == 'per_run':
        accounting['runs'][0]['recorded_actions'] += 1
    else:
        del packet['documents']['facts_summary']['execution_accounting']
    study = NeverStudy(tmp_path)
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == 'REJECTED' and study.calls == []
    assert 'EXECUTION_ACCOUNTING_CONTRADICTION' in result['hard_gate_errors']


def test_new_accounting_protocol_preserves_old_packet_and_semantic_decisions(tmp_path):
    original = source_packet(tmp_path)
    directory = Path(original['source_binding']['directory'])
    assert audit.prepare_audit_packet(directory, protocol=audit.PROTOCOL_V2) == original
    packet = audit.prepare_audit_packet(directory, protocol=audit.PROTOCOL_V21)
    study = SemanticStudy(tmp_path, packet['audit_facts'], verdict='REJECT')
    study.audit_output_mode = 'json_schema'
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == 'REJECTED' and len(study.calls) == 2
    assert all(not row['validation_errors'] for row in result['reviews'])
    sent = json.loads(study.calls[0][1][-1]['content'])
    assert 'execution_accounting' in sent['documents']['facts_summary']['value']
    assert all('fact_claims' not in row['review'] for row in result['reviews'])
    from ioabench.v5.ai_generation.audit_citations import verify_registered_result
    assert verify_registered_result(tmp_path / 'review')['raw_reviews_reconstructed'] == 2
