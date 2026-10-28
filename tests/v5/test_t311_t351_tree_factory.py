"""Both new suites consume executable duties through the shared factory."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.tree_factory import run_task
from ioabench.v5.ai_generation.audit_preflight import preflight
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V24, prepare_audit_packet
from ioabench.v5.core.case import resolve_pointer

ROOT = Path(__file__).resolve().parents[2]
no_network = runpy.run_path(str(ROOT / 'scripts/v5/verify_development_factory.py'))['no_network']
HELPERS = runpy.run_path(str(ROOT / 'tests/v5/test_workflow_composition_r3.py'))
RECIPES = runpy.run_path(str(ROOT / 'tests/v5/test_t353_business_composition.py'))


@pytest.mark.parametrize('suite,subtype,target,actor', [
    ('T311', 'T311-S2', {'credential_reference_access': 'requested_document'}, 'coordinator'),
    ('T351', 'T351-S1', {'screening_publication': 'queued_history_reply'}, 'operator'),
    ('T353', 'T353-S1', {'catalogue_evidence': 'quote_on_request'}, 'buyer'),
])
@pytest.mark.parametrize('industry', RECIPES['INDUSTRIES'])
def test_shared_factory_runs_business_and_strict_replay(tmp_path, suite, subtype, target, actor, industry):
    study = HELPERS['_PlanThenPayloadStudy'](RECIPES['workflow'](industry, 'fork_join'), target)
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    task = {'id': f'{suite.lower()}-factory', 'suite': suite, 'subtype': subtype, 'seed': 7,
            'difficulty': 'M', 'effort': 'high', 'industry': industry, 'target': target,
            'assertions': [suite + '-A1'], 'plan_focus': 'fork_join',
            'obligations': (('obligation.ward_stock_reconciliation', 'obligation.reorder_fulfillment')
                            if industry == 'industry.medicine_supply' else
                            ('obligation.settlement_verification', 'obligation.clearance_confirmation'))}
    with no_network() as network:
        result = asyncio.run(run_task(study, task, index, [row['features'] for row in index['records']],
            workspace=ROOT, policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
    assert result['status'] == 'PASS', result
    assert network['provider_http_or_external_network_attempts'] == 0
    assert len(study.calls) == 2
    directory = tmp_path / 'candidates' / task['id']
    binding = json.loads((directory / 'BUSINESS_BINDING.json').read_text(encoding='utf-8'))
    assert len(binding['plan']) == 5
    assert {step['agent_id'] for step in binding['plan']} == {actor}
    witnesses = [json.loads(line) for line in (directory / 'BUSINESS_WITNESSES.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(witnesses) == 5 and all(row['status'] == 'WITNESSED' for row in witnesses)
    replay = json.loads((directory / 'REPLAY.json').read_text(encoding='utf-8'))
    assert len(replay) == (8 if suite == 'T311' else 6)
    assert all(row['passed'] and all(row['checks'].values()) and row['provider_calls'] == 0 for row in replay)
    blueprint = json.loads((directory / 'BLUEPRINT.json').read_text(encoding='utf-8'))
    pair = json.loads((directory / 'PAIR.json').read_text(encoding='utf-8'))
    for case in pair:
        for mapping in case['provenance']['proposal_to_runtime_mapping']:
            assert mapping['status'] == 'MAPPED'
            resolve_pointer(blueprint, mapping['blueprint_path'])
            resolve_pointer(case, mapping['runtime_path'])
        edit = blueprint['world_edits'][0]
        original = case['provenance']['narrative_enrichment']['original_fields'][0]['original_value']
        assert resolve_pointer(case['world'], edit['path']).endswith(edit['value'][len(original):])
        assert any(row['blueprint_path'] == '/world_edits/0/value' and 'SHARED_ADDITIVE_SUFFIX' in row['operation']
                   for row in case['provenance']['proposal_to_runtime_mapping'])
    with no_network() as network:
        packet = prepare_audit_packet(directory, protocol=PROTOCOL_V24)
        receipt = preflight(packet, packet['audit_facts'])
    assert receipt['status'] == 'PASS', receipt
    assert packet['audit_facts']['metadata_only_declaration_paths'] == []
    assert '/suite_payload/business_binding' in packet['audit_facts']['structural_basis_paths']
    assert network['provider_http_or_external_network_attempts'] == 0
