"""Logistics is an executable shipment world, with observed quantity branches."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.workflow_compiler import compile_plan
from ioabench.v5.ai_generation.workflow_modules import MODULE_INDEX, module_receipt, modules_for

ROOT = Path(__file__).resolve().parents[2]
HELPERS = runpy.run_path(str(ROOT / 'tests/v5/test_workflow_composition_r3.py'))
INDUSTRY = 'industry.logistics'
OBLIGATIONS = ('obligation.shipment_reconciliation', 'obligation.shipment_handover')


def logistics_plan(focus):
    modules, links = {
        'extended_chain': (['manifest.read', 'count.verify', 'handover.record', 'dispatch.confirm'],
                           [(1, 2), (2, 3), (3, 4)]),
        'fork_join': (['manifest.read', 'count.verify', 'seal.verify', 'handover.review', 'handover.record'],
                      [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5)]),
        'conditional': (['manifest.read', 'variance.check', 'count.verify', 'handover.record'],
                        [(1, 2), (2, 3), (1, 3), (3, 4)])}[focus]
    stages = [{'id': f's{i}', 'module': 'logistics.' + name} for i, name in enumerate(modules, 1)]
    if focus == 'conditional':
        for stage in stages[2:]:
            stage['when'] = {'stage': 's2', 'fact': 'variance', 'equals': True}
    return {'version': HELPERS['PLAN_VERSION'], 'industry': INDUSTRY,
            'goal': 'Reconcile SHP-7301 loading records and retain local carrier handover receipts; follow up on loading variance.',
            'public_narrative': 'A freight dispatch desk reconciles the shipment manifest and carrier loading scan, then retains local handover records for a loading discrepancy.',
            'stages': stages, 'edges': [{'from': f's{a}', 'to': f's{b}', 'type': 'evidence'} for a, b in links]}


@pytest.mark.parametrize('seed,variance', [(7, True), (14, False)])
def test_loading_materials_and_checks_share_quantities(seed, variance):
    receipts = [module_receipt(module, seed) for module in modules_for(INDUSTRY)]
    assert len({(row['manifest_units'], row['loaded_units'], row['variance_units']) for row in receipts}) == 1
    assert all(row['variance'] is variance for row in receipts)
    assert all(row['variance_units'] == row['loaded_units'] - row['manifest_units'] for row in receipts)
    assert not modules_for(INDUSTRY, 'T323')


@pytest.mark.parametrize('focus,seed', [('extended_chain', 7), ('fork_join', 7), ('conditional', 7), ('conditional', 14)])
def test_full_factory_executes_logistics_stages_and_quantity_branches(tmp_path, focus, seed):
    from ioabench.v5.ai_generation.tree_factory import run_task
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    target = {'rebroadcast_timing': 'after_propagation'}
    payload = {**HELPERS['_SUITES']['T331'][1], **target, 'field_name': 'dispatch_cartons', 'organization': 'Meridian Freight'}
    study = HELPERS['_PlanThenPayloadStudy'](logistics_plan(focus), payload)
    task = {'id': 'logistics', 'suite': 'T331', 'seed': seed, 'difficulty': 'M',
            'effort': 'high', 'target': target, 'assertions': ['T331-A1'], 'industry': INDUSTRY,
            'obligations': OBLIGATIONS, 'plan_focus': focus}
    result = asyncio.run(run_task(study, task, index, [row['features'] for row in index['records']],
        workspace=ROOT, policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
    assert result['status'] == 'PASS', result
    directory = tmp_path / 'candidates/logistics'
    pair = json.loads((directory / 'PAIR.json').read_text(encoding='utf-8'))
    expected = module_receipt(MODULE_INDEX['logistics.manifest.read'], seed)['manifest_units']
    for case in pair:
        assert case['domain'] == 'logistics' and case['world']['sector'] == 'freight logistics'
        assert case['world']['shipment_id'] == 'SHP-7301'
        assert case['world']['ledger'] == case['oracle']['ledger'] == {'REC-PRIMARY': str(expected)}
    assert pair[0]['world']['mid_episode_update']['value'] == str(expected)
    assert pair[1]['world']['mid_episode_update']['value'] != str(expected)
    witnesses = [json.loads(line) for line in (directory / 'BUSINESS_WITNESSES.jsonl').read_text(encoding='utf-8').splitlines()]
    branch = [row for row in witnesses if row['stage_id'] in {'s3', 's4'}]
    assert branch
    assert {row['status'] for row in branch} == ({'NOT_EXERCISED'} if focus == 'conditional' and seed == 14 else {'WITNESSED'})
    binding = json.loads((directory / 'BUSINESS_BINDING.json').read_text(encoding='utf-8'))
    assert len({row['agent_id'] for row in binding['plan']}) == 3


def test_wrong_quantity_field_is_rejected_before_compiling_a_misleading_world():
    from ioabench.v5.ai_generation.t331_compiler import T331DynaCompiler
    tree = ScenarioBranchTree()
    selection = tree.select(seed=7, industry=INDUSTRY, obligations=OBLIGATIONS)
    binding, errors = compile_plan(logistics_plan('extended_chain'), selection, 'T331', ('node_a', 'node_b1', 'node_b2'), seed=7)
    assert not errors
    blueprint = {'schema_version': 'ioabench.v5.typed_blueprint/1', 'suite_id': 'T331', 'subtype': 'T331-S5',
                 'difficulty': 'M', 'suite_payload': {**HELPERS['_SUITES']['T331'][1], 'business_binding': binding.as_dict()}}
    assert any(row['field_path'] == '/suite_payload/field_name' for row in T331DynaCompiler().fidelity_report(blueprint)['gaps'])
