"""Business branch decisions agree with observed inventory and exception counts."""
from pathlib import Path
import runpy

import pytest

helpers = runpy.run_path(str(Path(__file__).with_name('test_workflow_composition_r3.py')))
from ioabench.v5.dynamic.business_tools import business_tools
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.workflow_compiler import compile_plan
from ioabench.v5.ai_generation.workflow_modules import MODULE_INDEX

FINANCE_CONDITIONAL = {'version': helpers['PLAN_VERSION'], 'industry': 'industry.payment_clearing',
    'goal': 'verify and clear flagged settlement legs',
    'stages': [{'id': 's1', 'module': 'finance.settlement.read'},
               {'id': 's2', 'module': 'finance.exception.check'},
               {'id': 's3', 'module': 'finance.receipt.verify',
                'when': {'stage': 's2', 'fact': 'exception', 'equals': True}},
               {'id': 's4', 'module': 'finance.clearance.post',
                'when': {'stage': 's2', 'fact': 'exception', 'equals': True}}],
    'edges': [{'from': 's1', 'to': 's2', 'type': 'order'},
              {'from': 's1', 'to': 's3', 'type': 'evidence'},
              {'from': 's2', 'to': 's3', 'type': 'enables'},
              {'from': 's3', 'to': 's4', 'type': 'enables'}]}


@pytest.mark.parametrize('seed', [0, 7])
@pytest.mark.parametrize('industry', ['medicine', 'finance'])
def test_real_read_and_check_receipts_describe_the_same_business_state(seed, industry):
    plan = helpers['MEDICINE_CONDITIONAL'] if industry == 'medicine' else FINANCE_CONDITIONAL
    tree = ScenarioBranchTree()
    obligations = tuple(sorted({MODULE_INDEX[s['module']].obligation for s in plan['stages']}))
    selection = tree.resolve(tree.select(seed=seed, industry=plan['industry'], obligations=obligations))
    binding, errors = compile_plan(plan, selection, 'T321', ('integration_agent',), seed=seed)
    assert not errors
    world = helpers['_t321_world'](binding)
    ctx, _ = helpers['_ctx'](world)
    tools = business_tools(world)
    if industry == 'medicine':
        stock = tools['lookup_stock'].handler(ctx, {'lot_id': 'LOT-2201'})
        check = tools['check_shortage'].handler(ctx, {'lot_id': 'LOT-2201'})
        assert check['margin_units'] == stock['on_hand'] - 100
        assert check['shortage'] is (check['margin_units'] < 0)
    else:
        settlement = tools['lookup_settlement'].handler(ctx, {'settlement_id': 'STL-5512'})
        check = tools['check_exception'].handler(ctx, {'settlement_id': 'STL-5512'})
        assert check['exception'] is (check['flagged_legs'] > 0)
        assert check['flagged_legs'] == settlement['flagged_legs']
        assert 0 <= check['flagged_legs'] <= settlement['legs']
