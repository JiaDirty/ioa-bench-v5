"""A missing business brief requires a new proposal, without inventing its text."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

from ioabench.models.types import ModelResponse
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.tree_factory import propose_workflow_plan


def test_generation_repairs_missing_business_context_with_a_distinct_request(tmp_path):
    helpers = runpy.run_path(str(Path(__file__).with_name('test_workflow_composition_r3.py')))
    complete = deepcopy(helpers['MEDICINE_LINEAR4'])
    original = deepcopy(complete)
    original.pop('goal')
    original.pop('public_narrative')
    messages, requests = [], []

    class Study:
        async def invoke(self, directory, request_id, prompt, params, **kwargs):
            messages.append(prompt)
            requests.append(request_id)
            plan = original if len(requests) == 1 else complete
            return ModelResponse(text=json.dumps({'workflow_plan': plan}), model_id='scripted',
                                 finish_reason='stop', usage={}, provider_metadata={})

    tree = ScenarioBranchTree()
    selection = tree.select(seed=7, industry='industry.medicine_supply', obligations=(
        'obligation.ward_stock_reconciliation', 'obligation.reorder_fulfillment'))
    result, calls = asyncio.run(propose_workflow_plan(Study(), SimpleNamespace(suite_id='T331'),
        {'target': {}, 'plan_focus': 'extended_chain'}, selection, tmp_path))
    assert len(calls) == 2 and requests[0] != requests[1]
    feedback = json.loads(messages[1][1]['content'])['failure_feedback']['compile_errors']
    assert set(feedback) == {'PLAN_GOAL_REQUIRED', 'PLAN_PUBLIC_NARRATIVE_REQUIRED'}
    assert result['goal'] == complete['goal'] and result['public_narrative'] == complete['public_narrative']
    assert result['stages'] == original['stages'] and result['edges'] == original['edges']
    assert 'goal' not in original and 'public_narrative' not in original
