"""Protocol reconciliation and approval queues reach the shared generation/audit path."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.audit_preflight import preflight
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V24, prepare_audit_packet
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.tree_factory import run_task
from ioabench.v5.core.case import resolve_pointer

ROOT = Path(__file__).resolve().parents[2]
HELPERS = runpy.run_path(str(ROOT / 'tests/v5/test_workflow_composition_r3.py'))
RECIPES = runpy.run_path(str(ROOT / 'tests/v5/test_t353_business_composition.py'))
no_network = runpy.run_path(str(ROOT / 'scripts/v5/verify_development_factory.py'))['no_network']


@pytest.mark.parametrize('suite,target,industry,actors', [
    ('T322', {'native_record_access': 'receipt_reference'}, 'industry.payment_clearing', {'reconciler'}),
    ('T343', {'activity_feed_access': 'handbook_query'}, 'industry.medicine_supply', {'operator_1', 'operator_2'}),
    ('T343', {'activity_feed_access': 'handbook_query'}, 'industry.payment_clearing', {'operator_1', 'operator_2'}),
])
def test_shared_factory_executes_business_and_retains_history_blocker(tmp_path, suite, target, industry, actors):
    study = HELPERS['_PlanThenPayloadStudy'](RECIPES['workflow'](industry, 'fork_join'), target)
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    task = {'id': suite.lower() + '-factory', 'suite': suite, 'subtype': suite + '-S1', 'seed': 7,
            'difficulty': 'M', 'effort': 'high', 'industry': industry, 'target': target,
            'assertions': [suite + '-A1'], 'plan_focus': 'fork_join',
            'obligations': (('obligation.ward_stock_reconciliation', 'obligation.reorder_fulfillment')
                            if industry == 'industry.medicine_supply' else
                            ('obligation.settlement_verification', 'obligation.clearance_confirmation'))}
    with no_network() as network:
        result = asyncio.run(run_task(study, task, index, [row['features'] for row in index['records']],
            workspace=ROOT, policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
        if suite == 'T322':
            assert result['status'] == 'REJECTED'
            assert result['failed_stage'] == 'HISTORY_INDETERMINATE'
            assert 'admission' not in result
            assert network['provider_http_or_external_network_attempts'] == 0
            return
        assert result['status'] == 'PASS', result
        directory = tmp_path / 'candidates' / task['id']
        binding = json.loads((directory / 'BUSINESS_BINDING.json').read_text(encoding='utf-8'))
        assert {step['agent_id'] for step in binding['plan']} == actors
        witnesses = [json.loads(line) for line in (directory / 'BUSINESS_WITNESSES.jsonl').read_text().splitlines()]
        assert len(witnesses) == 5 and all(row['status'] == 'WITNESSED' for row in witnesses)
        assertions = [json.loads(line) for line in (directory / 'ASSERTION_WITNESSES.jsonl').read_text().splitlines()]
        assert assertions and all(row['status'] == 'WITNESSED' for row in assertions)
        replay = json.loads((directory / 'REPLAY.json').read_text(encoding='utf-8'))
        assert len(replay) == 2 * len(suite_spec(suite, typed=True).policies)
        assert all(row['passed'] and all(row['checks'].values()) and row['provider_calls'] == 0 for row in replay)
        blueprint = json.loads((directory / 'BLUEPRINT.json').read_text(encoding='utf-8'))
        for case in json.loads((directory / 'PAIR.json').read_text(encoding='utf-8')):
            for mapping in case['provenance']['proposal_to_runtime_mapping']:
                assert mapping['status'] == 'MAPPED'
                resolve_pointer(blueprint, mapping['blueprint_path'])
                resolve_pointer(case, mapping['runtime_path'])
        packet = prepare_audit_packet(directory, protocol=PROTOCOL_V24)
        receipt = preflight(packet, packet['audit_facts'])
        assert receipt['status'] == 'PASS', receipt
        assert packet['audit_facts']['metadata_only_declaration_paths'] == []
    assert network['provider_http_or_external_network_attempts'] == 0
