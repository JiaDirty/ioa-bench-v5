"""Scorer evidence is inspectable context, never a semantic acceptance shortcut."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation import development_audit as audit
from ioabench.v5.ai_generation.audit_citations import citation_catalog, verify_registered_result
from ioabench.v5.evaluation import atomic_json
from tests.v5.test_observation_grounded_audit import GroupedStudy
from tests.v5.test_semantic_preflight import NeverStudy, source_packet


def scoring_packet(tmp_path):
    base = source_packet(tmp_path)
    source = Path(base['source_binding']['directory'])
    rows = json.loads((source / 'STRICT_REFERENCE_RESULTS.json').read_text(encoding='utf-8'))
    for row in rows:
        row.update(outcome={'fixture': 'outcome'}, monitor_report={'fixture': 'monitor'},
                   versions={'fixture': 'version'})
    atomic_json(source / 'STRICT_REFERENCE_RESULTS.json', rows)
    result = json.loads((source / 'RESULT.json').read_text(encoding='utf-8'))
    result['evidence_sha256']['STRICT_REFERENCE_RESULTS.json'] = audit._sha(source / 'STRICT_REFERENCE_RESULTS.json')
    atomic_json(source / 'RESULT.json', result)
    atomic_json(source / 'TERMINAL.json', {'result_sha256': canonical_sha256(result)})
    return source, audit.prepare_audit_packet(source, protocol=audit.PROTOCOL_V24)


def test_raw_scoring_and_compiler_evidence_preserved_without_changing_legacy(tmp_path):
    source, packet = scoring_packet(tmp_path)
    legacy = audit.prepare_audit_packet(source, protocol=audit.PROTOCOL_V23)
    before = deepcopy(legacy)
    raw = json.loads((source / 'STRICT_REFERENCE_RESULTS.json').read_text(encoding='utf-8'))
    fidelity = json.loads((source / 'FIDELITY.json').read_text(encoding='utf-8'))
    for index, run in enumerate(packet['documents']['execution']['runs']):
        assert run['evaluation'] == {key: raw[index][key] for key in ('score', 'outcome', 'monitor_report', 'versions')}
        assert 'evaluation' not in legacy['documents']['execution']['runs'][index]
    assert packet['documents']['schema']['compilation_fidelity'] == fidelity
    assert 'compilation_fidelity' not in legacy['documents']['schema']
    wrappers = {name: {'file': f'inputs/{name}.json', 'sha256': name, 'value': value}
                for name, value in packet['documents'].items()}
    catalog = citation_catalog(wrappers)
    ids = [row['evidence_id'] for row in catalog]
    assert len(ids) == len(set(ids))
    locations = {row['evidence_id']: row for row in catalog}
    for run in packet['documents']['execution']['tool_observation_ledger']:
        for position, observation in enumerate(run['observations']):
            ref = locations[observation['evidence_id']]
            assert ref['json_pointer'] == f"/tool_observation_ledger/{run['run_ordinal']}/observations/{position}"
            action = raw[run['run_ordinal']]['trace']['actions'][position]
            assert observation['evidence_id'] == f"OBS-R{run['run_ordinal']}-A{action['seq']}-{action['tool']}"
            assert observation['recorded_result'] == action['result']
    assert audit.prepare_audit_packet(source, protocol=audit.PROTOCOL_V23) == before


@pytest.mark.parametrize('verdict,status', [('ACCEPT', 'DEV_AUTO_AUDITED'), ('REJECT', 'REJECTED'), ('UNCERTAIN', 'QUARANTINED')])
def test_scorer_labels_do_not_override_model_verdict_and_native_reconstruction(tmp_path, verdict, status):
    _, packet = scoring_packet(tmp_path)
    study = GroupedStudy(tmp_path, packet['audit_facts'], verdict=verdict)
    study.audit_output_mode = 'json_schema'
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == status and len(study.calls) == 2
    assert all(not r['output_schema_errors'] and not r['validation_errors'] for r in result['reviews'])
    sent = json.loads(study.calls[0][1][-1]['content'])
    assert sent['documents']['execution']['value']['runs'][0]['evaluation'] == packet['documents']['execution']['runs'][0]['evaluation']
    assert any(r['json_pointer'] == '/runs/0/evaluation/score' for r in sent['citation_catalog'])
    assert any(r['evidence_id'].startswith('OBS-R0-A') for r in sent['citation_catalog'])
    assert verify_registered_result(tmp_path / 'review')['raw_reviews_reconstructed'] == 2
    assert asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review')) == result
    assert len(study.calls) == 2


@pytest.mark.parametrize('kind', ['score', 'outcome', 'mapping', 'observation_id'])
def test_relabelled_scoring_mapping_or_observation_cannot_reach_model(tmp_path, kind):
    _, packet = scoring_packet(tmp_path)
    execution = packet['documents']['execution']
    if kind in {'score', 'outcome'}:
        execution['runs'][0]['evaluation'][kind] = {'invented': True}
    elif kind == 'mapping':
        packet['documents']['schema']['compilation_fidelity'] = {'faithful': True, 'invented': True}
    else:
        execution['tool_observation_ledger'][0]['observations'][0]['evidence_id'] = 'OBS-R9-A999-invented'
    study = NeverStudy(tmp_path)
    result = asyncio.run(audit.audit_packet(study, packet, tmp_path / 'review'))
    assert result['status'] == 'REJECTED' and study.calls == []
    assert 'PACKET_SOURCE_MISMATCH' in result['hard_gate_errors']
    assert verify_registered_result(tmp_path / 'review')['raw_reviews_reconstructed'] == 0
