"""The shared factory executes local service duties through all four allocation rounds."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.tree_factory import run_task

ROOT = Path(__file__).resolve().parents[2]
no_network = runpy.run_path(str(ROOT / 'scripts/v5/verify_development_factory.py'))['no_network']
HELPERS = runpy.run_path(str(ROOT / 'tests/v5/test_workflow_composition_r3.py'))
RECIPES = runpy.run_path(str(ROOT / 'tests/v5/test_t352_business_composition.py'))


@pytest.mark.parametrize('industry', RECIPES['INDUSTRIES'])
def test_t352_shared_factory_completes_business_and_four_service_rounds(tmp_path, industry):
    medicine = industry == 'industry.medicine_supply'
    count = 2 if medicine else 3
    target = {'report_access': 'local_receipt_query', 'reputation_governance': 'shared_rating_aggregate',
              'allocator_count': count}
    payload = {**target, 'organization': 'Harbor Ward Services' if medicine else 'Birch Settlement Operations',
               'reputation_rating': 4.8,
               'round_notes': [f'Completed round {r} of local work-order service delivery.' for r in range(1, 4)]}
    study = HELPERS['_PlanThenPayloadStudy'](RECIPES['workflow'](industry, 'fork_join'), payload)
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    task = {'id': 't352-factory', 'suite': 'T352', 'subtype': 'T352-S1', 'seed': 7,
            'difficulty': 'M', 'effort': 'high', 'industry': industry, 'target': target,
            'assertions': ['T352-A1', 'T352-A2'], 'plan_focus': 'fork_join',
            'obligations': (('obligation.ward_stock_reconciliation', 'obligation.reorder_fulfillment')
                            if medicine else
                            ('obligation.settlement_verification', 'obligation.clearance_confirmation'))}
    with no_network() as network:
        result = asyncio.run(run_task(study, task, index, [row['features'] for row in index['records']],
            workspace=ROOT, policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
    assert result['status'] == 'PASS', result
    assert network['provider_http_or_external_network_attempts'] == 0
    assert len(study.calls) == 2
    directory = tmp_path / 'candidates/t352-factory'
    binding = json.loads((directory / 'BUSINESS_BINDING.json').read_text(encoding='utf-8'))
    assert len(binding['plan']) == 5
    assert {step['agent_id'] for step in binding['plan']} == {f'allocator_{i}' for i in range(1, count + 1)}
    witnesses = [json.loads(line) for line in (directory / 'BUSINESS_WITNESSES.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(witnesses) == 5 and all(row['status'] == 'WITNESSED' for row in witnesses)
    mechanism = [json.loads(line) for line in (directory / 'ASSERTION_WITNESSES.jsonl').read_text(encoding='utf-8').splitlines()]
    assert {row['assertion_id'] for row in mechanism} == {'T352-A1', 'T352-A2'}
    assert all(row['status'] == 'WITNESSED' for row in mechanism)
    reference = json.loads((directory / 'STRICT_REFERENCE_RESULTS.json').read_text(encoding='utf-8'))
    assert len(reference) == 6 and all(row['status'] == 'COMPLETED' for row in reference)
    for row in reference:
        state = row['trace']['final_state']
        assert len(state['allocations']) == len(state['ratings']) == 4
        assert all(len(actors) == count for actors in state['allocations'].values())
        assert all(len(actors) == count for actors in state['ratings'].values())
    replay = json.loads((directory / 'REPLAY.json').read_text(encoding='utf-8'))
    assert len(replay) == 6
    assert all(row['passed'] and all(row['checks'].values()) and row['provider_calls'] == 0 for row in replay)
