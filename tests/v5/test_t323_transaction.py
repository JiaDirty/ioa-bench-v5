"""The work order, registry documents and workflow receipts share one transaction."""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy

import pytest

helpers = runpy.run_path(str(Path(__file__).with_name('test_t323_composition.py')))
HELPERS, PROFILE, composed = (helpers[name] for name in ('HELPERS', 'PROFILE', 'composed'))
from ioabench.v5.ai_generation.compiler_capabilities import execution_witnesses
from ioabench.v5.ai_generation.pipeline import compile_and_gate
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic.t323_transaction import progress


def integrated(name='MEDICINE_LINEAR4', delivery='inline', seed=7):
    spec, blueprint, binding = composed(HELPERS[name], delivery, seed=seed)
    blueprint['suite_payload']['business_transaction'] = 'workflow_transaction_v1'
    return spec, blueprint, binding


@pytest.mark.parametrize('name,domain', [('MEDICINE_LINEAR4', 'clinical_admin'),
    ('MEDICINE_FORK_JOIN', 'clinical_admin'), ('MEDICINE_CONDITIONAL', 'clinical_admin'),
    ('FINANCE_FORK_JOIN', 'finance_ops')])
@pytest.mark.parametrize('delivery', ['inline', 'queued_after_turn'])
def test_domain_objects_receipts_progress_and_existing_safety(name, domain, delivery):
    spec, blueprint, binding = integrated(name, delivery)
    compiled = compile_and_gate(spec, blueprint, seed=7)
    runs = []
    for policy, model in spec.policies.items():
        for arm in ('control', 'risk'):
            case = compiled[arm]
            world = case.world
            transaction = world['business_transaction']
            assert case.domain == domain
            assert transaction['industry'] == binding.root
            assert transaction['transaction_id'] == world['work_order']['wo_id']
            document = world['registry_pre'][transaction['source_document']]
            assert document['business_objects'] == transaction['objects']
            assert document['subject'] == world['work_order']['subject']
            assert world['reconstruction']['document'] == document
            assert world['reconstruction']['accountability']['responsible_org'] == world['org']
            trace = asyncio.run(run_episode(case, spec.scenario_factory(), model, PROFILE, parameters={'temperature': 0.0}))
            assert trace.status == 'COMPLETED', trace.error_detail
            assert spec.scenario_factory().execution_fidelity(trace, world)['passed']
            score = spec.scorer(trace, case)
            assert score.safety == spec.expected[policy][case.arm]
            measured = trace.final_state['business_progress']
            assert measured == progress(world, trace.final_state)
            assert measured['business_goal_completed'] is (policy != 'naive')
            assert bool(measured['pending_stages']) is (policy == 'naive')
            assert all(a.result['transaction_id'] == transaction['transaction_id'] for a in trace.actions
                if a.tool in {step['tool'] for step in binding.plan} and a.status == 'ok')
            if policy == 'naive':
                assert any(a.tool == 'execute' and a.status == 'ok' for a in trace.actions)
            runs.append({'arm': case.arm, 'policy': policy, 'trace': trace, 'world': world})
    assert all(r['status'] == 'WITNESSED' for r in execution_witnesses(['T323-A3'], runs))


def test_untaken_branch_can_complete_without_fabricating_receipts():
    spec, blueprint, _ = integrated('MEDICINE_CONDITIONAL', seed=0)
    case = spec.adapter.compile_pair(blueprint, seed=0)[1]
    trace = asyncio.run(run_episode(case, spec.scenario_factory(), spec.policies['witness'], PROFILE, parameters={'temperature': 0.0}))
    measured = trace.final_state['business_progress']
    assert measured['completed_stages'] == ['s1', 's2']
    assert measured['skipped_stages'] == ['s3', 's4']
    assert measured['pending_stages'] == [] and measured['business_goal_completed']


@pytest.mark.parametrize('mutation', ['receipt', 'progress', 'release', 'source'])
def test_integrated_witness_rejects_forged_or_missing_linkage(mutation):
    spec, blueprint, _ = integrated()
    case = spec.adapter.compile_pair(blueprint, seed=7)[1]
    trace = asyncio.run(run_episode(case, spec.scenario_factory(), spec.policies['witness'], PROFILE, parameters={'temperature': 0.0}))
    world = deepcopy(case.world)
    if mutation == 'receipt':
        next(a for a in trace.actions if a.tool == 'lookup_stock').result['transaction_id'] = 'another-order'
        assert not spec.scenario_factory().execution_fidelity(trace, world)['passed']
    elif mutation == 'progress':
        trace.final_state['business_progress']['business_goal_completed'] = False
        assert not spec.scenario_factory().execution_fidelity(trace, world)['passed']
    elif mutation == 'release':
        next(a for a in trace.actions if a.tool == 'execute').result.pop('business_progress')
    else:
        world['business_transaction']['source_document'] = 'another-document'
    run = {'arm': case.arm, 'policy': 'witness', 'trace': trace, 'world': world}
    assert execution_witnesses(['T323-A3'], [run])[0]['status'] == 'DESIGN_EXECUTION_FIDELITY_FAIL'


def test_transaction_profile_requires_a_real_plan():
    spec, blueprint, _ = integrated()
    del blueprint['suite_payload']['business_binding']
    assert spec.adapter.fidelity_report(blueprint)['gaps']


def test_transaction_rebinding_preserves_the_allowed_neutral_narrative_suffix():
    spec, blueprint, _ = integrated()
    suffix = ' Context: morning operations desk.'
    blueprint['world_edits'][0]['value'] += suffix
    for case in spec.adapter.compile_pair(blueprint, seed=7):
        world = case.world
        assert world['work_order']['subject'].endswith(suffix)
        assert world['reconstruction']['document']['subject'] == world['work_order']['subject']


@pytest.mark.parametrize('integrate', [False, True])
def test_shared_factory_records_program_owned_transaction_profile(tmp_path, integrate):
    import json
    from ioabench.v5.ai_generation.tree_factory import run_task
    plan = HELPERS['FINANCE_FORK_JOIN']
    study = HELPERS['_PlanThenPayloadStudy'](plan, {'reconstruction_delivery': 'queued_after_turn',
        'business_transaction': 'MODEL_CANNOT_SET_THIS'})
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    task = {'id': 'R3-TEST-T323-TRANSACTION', 'suite': 'T323', 'seed': 7, 'difficulty': 'M',
        'effort': 'high', 'target': {'reconstruction_delivery': 'queued_after_turn'},
        'assertions': ['T323-A1', 'T323-A2'] + (['T323-A3'] if integrate else []), 'industry': plan['industry'],
        'business_transaction': integrate}
    row = asyncio.run(run_task(study, task, index, [r['features'] for r in index['records']],
        workspace=HELPERS['ROOT'], policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
    assert row['status'] == 'PASS', row
    ir = json.loads((tmp_path / 'candidates' / task['id'] / 'MECHANISM_IR.json').read_text())
    if integrate:
        assert ir['field_provenance']['suite_payload.business_transaction'] == 'PROGRAM_TRUTH'
        assert ir['suite_payload']['business_transaction'] == 'workflow_transaction_v1'
    else:
        assert 'business_transaction' not in ir['suite_payload']
