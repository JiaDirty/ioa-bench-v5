"""Composed accountability work orders retain source reconstruction and paired safety."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import runpy

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler
from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses, execution_witnesses, structural_cells
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.core.engine import run_episode

HELPERS = runpy.run_path(str(Path(__file__).with_name('test_workflow_composition_r3.py')))
PROFILE = ModelProfile('scripted', 'reference-policy', {}, {}, 'REFERENCE_POLICY')


def composed(plan, delivery='inline', difficulty='M', seed=7):
    from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
    from ioabench.v5.ai_generation.workflow_modules import MODULE_INDEX
    from ioabench.v5.ai_generation.workflow_compiler import compile_plan
    tree = ScenarioBranchTree()
    obligations = tuple(sorted({MODULE_INDEX[s['module']].obligation for s in plan['stages']}))
    selection = tree.resolve(tree.select(seed=seed, industry=plan['industry'], obligations=obligations))
    binding, errors = compile_plan(plan, selection, 'T323', ('operator',), seed=seed)
    assert not errors, errors
    spec = suite_spec('T323', typed=True)
    blueprint = spec.adapter.default_blueprint(seed=seed, difficulty=difficulty)
    blueprint['suite_payload'].update(reconstruction_delivery=delivery, business_binding=binding.as_dict())
    return spec, blueprint, binding


@pytest.mark.parametrize('name', ['MEDICINE_LINEAR4', 'MEDICINE_FORK_JOIN', 'MEDICINE_CONDITIONAL', 'FINANCE_FORK_JOIN'])
@pytest.mark.parametrize('delivery', ['inline', 'queued_after_turn'])
def test_actual_business_receipts_and_original_safety_contrast(name, delivery):
    spec, blueprint, binding = composed(HELPERS[name], delivery)
    compiled = compile_and_gate(spec, blueprint, seed=7)
    runs = []
    for policy, model in spec.policies.items():
        for arm in ('control', 'risk'):
            case = compiled[arm]
            trace = asyncio.run(run_episode(case, spec.scenario_factory(), model, PROFILE, parameters={'temperature': 0.0}))
            assert trace.status == 'COMPLETED', trace.error_detail
            assert spec.scenario_factory().execution_fidelity(trace, case.world)['passed']
            assert spec.scorer(trace, case).safety == spec.expected[policy][case.arm]
            stages = {a.result['stage_id'] for a in trace.actions if a.status == 'ok' and a.result.get('stage_id')}
            assert stages == (set() if policy == 'naive' else {s['stage_id'] for s in binding.plan})
            if policy != 'naive':
                assert spec.scorer(trace, case).utility
            runs.append({'arm': case.arm, 'policy': policy, 'trace': trace, 'world': case.world})
    assert all(r['status'] == 'WITNESSED' for r in business_witnesses(binding, runs))
    assertions = ['T323-A1'] + (['T323-A2'] if delivery == 'queued_after_turn' else [])
    assert all(r['status'] == 'WITNESSED' for r in execution_witnesses(assertions, runs))


@pytest.mark.parametrize('difficulty', ['E', 'M', 'H'])
@pytest.mark.parametrize('delivery', ['inline', 'queued_after_turn'])
def test_legacy_blueprints_remain_byte_equal_to_bounded_compiler(difficulty, delivery):
    old, current = BoundedWorldCompiler('T323-DYNA'), suite_spec('T323', typed=True).adapter
    blueprint = old.default_blueprint(seed=317, difficulty=difficulty)
    blueprint['suite_payload']['reconstruction_delivery'] = delivery
    assert [c.as_dict() for c in current.compile_pair(blueprint, seed=317)] == [c.as_dict() for c in old.compile_pair(blueprint, seed=317)]


def test_false_condition_is_not_counted_as_executed_diversity():
    spec, blueprint, binding = composed(HELPERS['MEDICINE_CONDITIONAL'], seed=0)
    compiled = compile_and_gate(spec, blueprint, seed=0)
    runs = []
    for arm in ('control', 'risk'):
        case = compiled[arm]
        trace = asyncio.run(run_episode(case, spec.scenario_factory(), spec.policies['witness'], PROFILE, parameters={'temperature': 0.0}))
        assert {a.result['stage_id'] for a in trace.actions if a.result.get('stage_id')} == {'s1', 's2'}
        runs.append({'arm': case.arm, 'policy': 'witness', 'trace': trace, 'world': case.world})
    assert [r['status'] for r in business_witnesses(binding, runs)] == ['WITNESSED', 'WITNESSED', 'NOT_EXERCISED', 'NOT_EXERCISED']


def test_binding_integrity_and_shared_arm_boundary():
    spec, blueprint, _ = composed(HELPERS['MEDICINE_LINEAR4'])
    control, risk = spec.adapter.compile_pair(blueprint, seed=7)
    changed = deepcopy(risk.world)
    changed['business_binding']['stages'] = []
    assert spec.adapter.verify_arm_delta(control, replace(risk, world=changed))
    blueprint['suite_payload']['business_binding']['plan'][0]['tool'] = 'invented_tool'
    assert spec.adapter.fidelity_report(blueprint)['gaps']


def test_shared_factory_consumes_t323_ir_and_preflights_sealed_pair(tmp_path):
    plan = HELPERS['FINANCE_FORK_JOIN']
    study = HELPERS['_PlanThenPayloadStudy'](plan, {'reconstruction_delivery': 'queued_after_turn'})
    row = HELPERS['_run_r3'](tmp_path, study, 'T323', {'reconstruction_delivery': 'queued_after_turn'},
        plan, assertions=['T323-A1', 'T323-A2'], seed=7)
    assert row['status'] == 'PASS', row
    directory = tmp_path / 'candidates/R3-TEST-T323'
    assert len(json.loads((directory / 'REPLAY.json').read_text())) == 6
    from ioabench.v5.ai_generation.development_audit import prepare_audit_packet, PROTOCOL_V21
    from ioabench.v5.ai_generation.audit_facts import facts_from_documents
    from ioabench.v5.ai_generation.audit_preflight import preflight
    packet = prepare_audit_packet(directory, protocol=PROTOCOL_V21)
    facts = facts_from_documents(packet['documents'], base=packet['audit_facts'])
    facts['oracle_leakage_present'] = packet['audit_facts']['oracle_leakage_present']
    assert preflight(packet, facts)['status'] == 'PASS'


def test_capability_lattice_is_existing_reconstruction_diversity():
    cells = structural_cells('T323')
    assert len(cells['cells']) == 2
    assert cells['new_factor_cells'] == []


@pytest.mark.parametrize('mutation,assertion', [
    ('no_execute', 'T323-A1'), ('failed_execute', 'T323-A1'), ('late_lookup', 'T323-A1'),
    ('wrong_source', 'T323-A1'), ('wrong_document', 'T323-A1'), ('no_notice', 'T323-A1'),
    ('unobserved_notice', 'T323-A1'), ('no_request', 'T323-A2'), ('inline_result', 'T323-A2'),
    ('no_delivery', 'T323-A2'), ('wrong_delivery', 'T323-A2'), ('unobserved_record', 'T323-A2'),
    ('early_delivery', 'T323-A2'), ('early_lookup', 'T323-A2')])
def test_mechanism_witnesses_reject_missing_late_failed_or_forged_proof(mutation, assertion):
    spec, blueprint, _ = composed(HELPERS['FINANCE_FORK_JOIN'], 'queued_after_turn')
    case = spec.adapter.compile_pair(blueprint, seed=7)[1]
    trace = asyncio.run(run_episode(case, spec.scenario_factory(), spec.policies['witness'], PROFILE, parameters={'temperature': 0.0}))
    execute = next(a for a in trace.actions if a.tool == 'execute')
    ref = case.world['reconstruction']['accountability']['source_document']
    lookup = next(a for a in trace.actions if a.tool == 'lookup_document' and a.arguments['document_ref'] == ref)
    if mutation == 'no_execute':
        trace.actions.remove(execute)
    elif mutation == 'failed_execute':
        execute.status = 'error'
    elif mutation == 'late_lookup':
        lookup.seq = execute.seq + 1
    elif mutation == 'wrong_source':
        lookup.result['document_ref'] = 'wrong-source'
    elif mutation == 'wrong_document':
        lookup.result['document'] = {'subject': 'another instruction'}
    elif mutation == 'no_notice':
        trace.events = [e for e in trace.events if e['kind'] != 'registry_reindex_delivered']
    elif mutation == 'unobserved_notice':
        for record in trace.records:
            record['request']['messages'] = [m for m in record['request']['messages'] if m.get('content') != case.world['reindex_notice']]
    elif mutation == 'no_request':
        trace.actions = [a for a in trace.actions if a.tool != 'request_reconstruction']
    elif mutation == 'inline_result':
        next(a for a in trace.actions if a.tool == 'request_reconstruction').result['accountability'] = case.world['reconstruction']['accountability']
    elif mutation == 'no_delivery':
        trace.events = [e for e in trace.events if e['kind'] != 'reconstruction_delivered']
    elif mutation == 'wrong_delivery':
        next(e for e in trace.events if e['kind'] == 'reconstruction_delivered')['payload']['document_ref'] = 'wrong-source'
    elif mutation == 'early_delivery':
        next(e for e in trace.events if e['kind'] == 'reconstruction_delivered')['turn'] = 0
    elif mutation == 'early_lookup':
        lookup.seq = next(e for e in trace.events if e['kind'] == 'reconstruction_delivered')['payload']['after_actions']
    elif mutation == 'unobserved_record':
        for record in trace.records:
            record['request']['messages'] = [m for m in record['request']['messages'] if 'Registry desk: the reconstructed' not in m.get('content', '')]
    run = {'arm': case.arm, 'policy': 'witness', 'trace': trace, 'world': case.world}
    assert execution_witnesses([assertion], [run])[0]['status'] == 'DESIGN_EXECUTION_FIDELITY_FAIL'
