"""Delegated record review reaches the common factory and audit evidence path."""
import asyncio
import json
from pathlib import Path
import runpy

import pytest

from ioabench.v5.ai_generation.audit_preflight import preflight
from ioabench.v5.ai_generation.development_audit import PROTOCOL_V24, prepare_audit_packet
from ioabench.v5.ai_generation.tree_factory import run_task
from ioabench.v5.core.case import resolve_pointer
from test_t313_business_composition import workflow

ROOT = Path(__file__).resolve().parents[2]
HELPERS = runpy.run_path(str(ROOT / 'tests/v5/test_workflow_composition_r3.py'))
no_network = runpy.run_path(str(ROOT / 'scripts/v5/verify_development_factory.py'))['no_network']


@pytest.mark.parametrize('focus,seed', [('extended_chain', 7), ('fork_join', 7), ('conditional', 7), ('conditional', 0)])
def test_shared_factory_retains_real_delegation_and_both_review_branch_outcomes(tmp_path, focus, seed):
    study = HELPERS['_PlanThenPayloadStudy'](workflow(focus), {'chain_projection': 'subgrant_index'})
    index = json.loads(HELPERS['SEALED_INDEX'].read_text(encoding='utf-8'))
    task = {'id': f't313-{focus}-{seed}', 'suite': 'T313', 'subtype': 'T313-S4', 'seed': seed,
        'difficulty': 'M', 'effort': 'high', 'industry': 'industry.payment_clearing',
        'target': {'chain_projection': 'subgrant_index'}, 'assertions': ['T313-A1'], 'plan_focus': focus,
        'obligations': ('obligation.settlement_verification', 'obligation.clearance_confirmation')}
    with no_network() as network:
        result = asyncio.run(run_task(study, task, index, [row['features'] for row in index['records']],
            workspace=ROOT, policy=HELPERS['_policy'](), out=tmp_path, route='compositional_r3'))
        assert result['status'] == 'PASS', result
        directory = tmp_path / 'candidates' / task['id']
        replay = json.loads((directory / 'REPLAY.json').read_text(encoding='utf-8'))
        assert len(replay) == 6 and all(row['passed'] and all(row['checks'].values()) for row in replay)
        assertions = [json.loads(line) for line in (directory / 'ASSERTION_WITNESSES.jsonl').read_text().splitlines()]
        assert assertions and all(row['status'] == 'WITNESSED' for row in assertions)
        witnesses = [json.loads(line) for line in (directory / 'BUSINESS_WITNESSES.jsonl').read_text().splitlines()]
        assert witnesses
        assert all(row['status'] == ('NOT_EXERCISED'
                   if focus == 'conditional' and seed == 0 and row['stage_id'] not in {'s1', 's2'}
                   else 'WITNESSED') for row in witnesses)
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


def test_read_only_route_has_bounded_capacity_without_commit_modules():
    capacity = runpy.run_path(str(ROOT / 'scripts/v5/workflow_capacity.py'))
    group = capacity['capacity_group']('T313', 'industry.payment_clearing', [])
    assert group['bounded_graph_capacity'] > 1
    assert all(step['capability'] in {'read', 'verify', 'check'}
               for row in group['graphs'] for step in row['binding']['plan'])
