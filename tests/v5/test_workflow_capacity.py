"""Capacity is bounded and preserves failed history without inventing novelty."""
import json
from pathlib import Path
import runpy

import pytest

capacity = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/v5/workflow_capacity.py'))


@pytest.mark.parametrize('industry', capacity['INDUSTRIES'])
def test_bounded_capacity_exhaustion_uses_actual_graph_identity(industry):
    suite = 'T331' if industry == 'industry.logistics' else 'T323'
    group = capacity['capacity_group'](suite, industry, [])
    assert group['bounded_graph_capacity'] > 1
    assert group['unexplored_in_grammar'] == group['bounded_graph_capacity']
    observed = [{'suite': suite, 'industry': industry, 'family_id': row['family_id']}
                for row in group['graphs']]
    exhausted = capacity['capacity_group'](suite, industry, observed)
    assert exhausted['status'] == 'BOUNDED_GRAMMAR_EXHAUSTED'
    assert exhausted['recommendation'] is None and exhausted['unexplored_in_grammar'] == 0
    assert exhausted['bounded_graph_capacity'] == group['bounded_graph_capacity']
    assert any(step.get('when') for graph in group['graphs'] for step in graph['workflow_plan']['stages'])


def test_rejected_and_quarantined_graphs_remain_observed(tmp_path):
    group = capacity['capacity_group']('T323', capacity['INDUSTRIES'][1], [])
    for status in ('REJECTED', 'QUARANTINED'):
        directory = tmp_path / 'trial/candidates' / status
        directory.mkdir(parents=True)
        binding = json.loads(json.dumps(group['graphs'][0]['binding']))
        for step in binding['plan']:
            if step.get('when') is None:
                step.pop('when', None)  # Optional in retained older plans; keep actual conditions.
        (directory / 'BUSINESS_BINDING.json').write_text(json.dumps(binding), encoding='utf-8')
        (directory / 'MANIFEST.json').write_text('{}', encoding='utf-8')
        (directory / 'RESULT.json').write_text(json.dumps({'status': status}), encoding='utf-8')
    records = capacity['observed_graphs'](tmp_path)
    assert {r['candidate_status'] for r in records} == {'REJECTED', 'QUARANTINED'}
    next_group = capacity['capacity_group']('T323', capacity['INDUSTRIES'][1], records)
    assert next_group['previously_compiled_in_grammar'] == 1
    assert next_group['unexplored_in_grammar'] == group['bounded_graph_capacity'] - 1
    assert next_group['recommendation'] != group['graphs'][0]['workflow_plan']
    original = {'suite': 'T323', 'industry': capacity['INDUSTRIES'][1], 'covered_workflows': []}
    tasks = capacity['add_observed_coverage']([original], {'groups': [next_group], 'observed_candidates': records})
    assert original['covered_workflows'] == []
    assert len(tasks[0]['covered_workflows']) == 1
    assert tasks[0]['covered_workflows'][0]['historical_admission'] is None
    assert [step['when'] for step in tasks[0]['covered_workflows'][0]['stages']] == [
        step.get('when') for step in group['graphs'][0]['binding']['plan']]
    assert tasks[0]['bounded_workflow_capacity']['unexplored_in_grammar'] == next_group['unexplored_in_grammar']


def test_trial_preparation_freezes_capacity_and_passes_failed_graphs_to_prompt(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / 'scripts/v5'
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / 'tree_factory_trial.py'))
    globals_ = trial['prepare'].__globals__
    monkeypatch.setitem(globals_, 'historical_pool', lambda: [])
    monkeypatch.setitem(globals_, 'historical_failure_counts', lambda: {})
    report = {'groups': [], 'observed_candidates': [], 'scope': 'fixture'}
    monkeypatch.setitem(globals_, 'capacity_report', lambda root: report)
    def covered(tasks, evidence):
        assert evidence is report
        return [dict(t, covered_workflows=[{'family_id': 'rejected-graph', 'stages': [],
                                          'historical_candidate_status': 'REJECTED'}]) for t in tasks]
    monkeypatch.setitem(globals_, 'add_observed_coverage', covered)
    plan = trial['prepare'](tmp_path / 'prepared', suites=['T323'])
    assert plan['version'] == 'ioabench.v5.main-quality-trial/2.13.0'
    assert plan['workflow_capacity_sha256'] == trial['canonical_sha256'](report)
    assert json.loads((tmp_path / 'prepared/WORKFLOW_CAPACITY.json').read_text()) == report
    assert all(t['covered_workflows'][0]['historical_candidate_status'] == 'REJECTED' for t in plan['tasks'])
    assert all(t['business_transaction'] for t in plan['tasks'])
    # A frozen planning report is a run input, including on terminal resume.
    (tmp_path / 'prepared/TRIAL_SUMMARY.json').write_text('{}', encoding='utf-8')
    (tmp_path / 'prepared/WORKFLOW_CAPACITY.json').write_text('{"tampered":true}', encoding='utf-8')
    import asyncio
    with pytest.raises(AssertionError):
        asyncio.run(trial['run'](tmp_path / 'prepared'))


def test_generator_sees_attempted_history_without_admission_claim(tmp_path):
    import asyncio
    from types import SimpleNamespace
    from ioabench.models.types import ModelResponse
    from ioabench.v5.ai_generation.tree_factory import propose_workflow_plan
    from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
    from ioabench.v5.ai_generation.workflow_modules import modules_for
    industry = capacity['INDUSTRIES'][0]
    plan = next(capacity['dependency_plans'](industry, 'T323'))
    plan['public_narrative'] = 'The pharmacy and supplier reconcile a ward stock record before retaining the local replenishment receipt.'
    tree = ScenarioBranchTree()
    selection = tree.resolve(tree.select(seed=7, industry=industry,
        obligations=tuple(sorted({m.obligation for m in modules_for(industry, 'T323')}))))
    class Study:
        async def invoke(self, directory, request_id, messages, params, **kwargs):
            payload = json.loads(messages[1]['content'])
            assert payload['covered_workflows'][0]['historical_candidate_status'] == 'REJECTED'
            assert any('do not establish successful execution or admission' in r for r in payload['requirements'])
            return ModelResponse(text=json.dumps({'workflow_plan': plan}), model_id='scripted',
                                 finish_reason='stop', usage={}, provider_metadata={})
    result, calls = asyncio.run(propose_workflow_plan(Study(), SimpleNamespace(suite_id='T323'),
        {'target': {}, 'covered_workflows': [{'family_id': 'attempt', 'historical_candidate_status': 'REJECTED'}]},
        selection, tmp_path))
    assert result['stages'] == plan['stages'] and len(calls) == 1
