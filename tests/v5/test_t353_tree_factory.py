"""The shared factory executes procurement duties and preserves quote evidence."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.tree_factory import run_task

ROOT = Path(__file__).resolve().parents[2]
no_network = runpy.run_path(str(ROOT / 'scripts/v5/verify_development_factory.py'))['no_network']
HELPERS = runpy.run_path(str(ROOT / 'tests/v5/test_workflow_composition_r3.py'))
RECIPES = runpy.run_path(str(ROOT / 'tests/v5/test_t353_business_composition.py'))


@pytest.mark.parametrize('industry', RECIPES['INDUSTRIES'])
def test_t353_shared_factory_runs_business_and_original_quote_chain(tmp_path, industry):
    plan = RECIPES['workflow'](industry, 'fork_join')
    target = {'catalogue_evidence': 'quote_on_request'}
    study = HELPERS['_PlanThenPayloadStudy'](plan, target)
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    task = {'id': 't353-factory', 'suite': 'T353', 'subtype': 'T353-S1', 'seed': 7,
            'difficulty': 'M', 'effort': 'high', 'industry': industry, 'target': target,
            'assertions': ['T353-A1'], 'plan_focus': 'fork_join',
            'obligations': (('obligation.ward_stock_reconciliation', 'obligation.reorder_fulfillment')
                            if industry == 'industry.medicine_supply' else
                            ('obligation.settlement_verification', 'obligation.clearance_confirmation'))}
    with no_network() as network:
        result = asyncio.run(run_task(study, task, index, [row['features'] for row in index['records']],
            workspace=ROOT, policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
    assert result['status'] == 'PASS', result
    assert network['provider_http_or_external_network_attempts'] == 0
    assert len(study.calls) == 2
    directory = tmp_path / 'candidates/t353-factory'
    binding = json.loads((directory / 'BUSINESS_BINDING.json').read_text(encoding='utf-8'))
    assert len(binding['plan']) == 5
    assert {step['agent_id'] for step in binding['plan']} == {'buyer'}
    witnesses = [json.loads(line) for line in (directory / 'BUSINESS_WITNESSES.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(witnesses) == 5 and all(row['status'] == 'WITNESSED' for row in witnesses)
    mechanism = [json.loads(line) for line in (directory / 'ASSERTION_WITNESSES.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(mechanism) == 1 and mechanism[0]['assertion_id'] == 'T353-A1'
    assert mechanism[0]['status'] == 'WITNESSED'
    replay = json.loads((directory / 'REPLAY.json').read_text(encoding='utf-8'))
    assert len(replay) == 6
    assert all(row['passed'] and all(row['checks'].values()) and row['provider_calls'] == 0 for row in replay)
