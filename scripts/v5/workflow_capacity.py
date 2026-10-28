"""Inventory bounded catalog dependency graphs before spending on enrichment.

This grammar uses each module at most once, includes read/verify/commit, and
orders every selected verification/check before commit. Conditional modules
gate commit and its descendants. Other legal WorkflowPlans remain possible.
"""
from __future__ import annotations

import argparse
from graphlib import TopologicalSorter
from itertools import combinations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.v5.verify_development_factory import no_network, read, sha
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.tree_factory import assemble_blueprint, runtime_agent_ids
from ioabench.v5.ai_generation.workflow_compiler import WORKFLOW_PLAN_VERSION, compile_plan
from ioabench.v5.ai_generation.workflow_modules import modules_for, WORKFLOW_MODULES_VERSION
from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, workflow_graph
from ioabench.v5.evaluation import atomic_json

VERSION = 'ioabench.v5.workflow-capacity/1.5.0'
SUITES = ('T311', 'T312', 'T313', 'T321', 'T322', 'T323', 'T331', 'T343', 'T351', 'T352', 'T353', 'T362')
INDUSTRIES = ('industry.medicine_supply', 'industry.payment_clearing', 'industry.logistics')


def dependency_plans(industry, suite):
    """Enumerate this finite grammar, not the capacity of all possible DAGs."""
    catalog = modules_for(industry, suite)
    for size in range(3, len(catalog) + 1):
        for selected in combinations(catalog, size):
            required = {'read', 'verify'} if suite == 'T313' else {'read', 'verify', 'commit'}
            if not required <= {m.capability for m in selected}:
                continue
            by_event = {m.event: m for m in selected}
            if any(not set(m.requires) <= by_event.keys() for m in selected):
                continue
            dependencies = {m.event: set(m.requires) for m in selected}
            if suite == 'T313':
                terminal = next((m for m in selected if m.module_id == 'finance.clearance.review'),
                                next(m for m in reversed(selected) if m.capability == 'verify'))
                dependencies[terminal.event].update(m.event for m in selected
                    if m.event != terminal.event and m.capability in {'verify', 'check'})
            else:
                terminal = next(m for m in selected if m.capability == 'commit')
                dependencies[terminal.event].update(m.event for m in selected if m.capability in {'verify', 'check'})
            order = list(TopologicalSorter(dependencies).static_order())
            ids = {event: f's{i + 1}' for i, event in enumerate(order)}
            condition = next((m for m in selected if m.conditional_fact), None)
            gated = {terminal.event}
            for event in order:
                if dependencies[event] & gated:
                    gated.add(event)
            stages = []
            for event in order:
                module = by_event[event]
                stage = {'id': ids[event], 'module': module.module_id}
                if condition and event in gated:
                    stage['when'] = {'stage': ids[condition.event], 'fact': condition.conditional_fact, 'equals': True}
                stages.append(stage)
            yield {'version': WORKFLOW_PLAN_VERSION, 'industry': industry,
                   'goal': ('Read and summarize the delegated settlement without posting a payment.' if suite == 'T313'
                            else 'Verify the local business record before committing and retain selected follow-up receipts.'),
                   'stages': stages, 'edges': [
                       {'from': ids[source], 'to': ids[target], 'type': 'order'}
                       for target in order for source in sorted(dependencies[target])]}


def observed_graphs(history_root):
    """Include every retained compiled candidate, regardless of admission."""
    records = []
    for path in sorted(history_root.rglob('BUSINESS_BINDING.json')):
        if path.parent.parent.name != 'candidates':
            continue
        manifest_path, result_path = path.parent / 'MANIFEST.json', path.parent / 'RESULT.json'
        if not manifest_path.exists() or not result_path.exists():
            continue
        binding = read(path)
        if binding['suite'] not in SUITES or binding['root'] not in INDUSTRIES:
            continue
        result = read(result_path)
        records.append({'suite': binding['suite'], 'industry': binding['root'],
            'family_id': canonical_graph(workflow_graph(binding))['family_id'],
            'binding_file': str(path.resolve()), 'binding_sha256': sha(path),
            'result_file': str(result_path.resolve()), 'result_sha256': sha(result_path),
            'manifest_file': str(manifest_path.resolve()), 'manifest_sha256': sha(manifest_path),
            'candidate_status': result['status'], 'admission': result.get('admission')})
    return records


def capacity_group(suite, industry, observed):
    task = {'seed': 7, 'difficulty': 'M', 'target': {},
            'subtype': 'T312-S2' if suite == 'T312' else 'T331-S5'}
    spec = suite_spec(suite, typed=True)
    blueprint = assemble_blueprint(spec, {}, task)
    base = spec.adapter.compile_pair(blueprint, seed=7)[0]
    actors = runtime_agent_ids(spec, base)
    tree = ScenarioBranchTree()
    obligations = tuple(sorted({m.obligation for m in modules_for(industry, suite)}))
    selection = tree.resolve(tree.select(seed=7, industry=industry, obligations=obligations))
    seen = {row['family_id'] for row in observed if (row['suite'], row['industry']) == (suite, industry)}
    candidates = {}
    for plan in dependency_plans(industry, suite):
        binding, errors = compile_plan(plan, selection, suite, actors, seed=7)
        assert not errors, errors
        family = canonical_graph(workflow_graph(binding))['family_id']
        candidates.setdefault(family, {'family_id': family, 'previously_compiled': family in seen,
                                      'workflow_plan': plan, 'binding': binding.as_dict()})
    uncovered = sorted(set(candidates) - seen)
    return {'suite': suite, 'industry': industry, 'runtime_actor_ids': list(actors),
            'bounded_graph_capacity': len(candidates), 'previously_compiled_in_grammar': len(set(candidates) & seen),
            'unexplored_in_grammar': len(uncovered), 'observed_outside_grammar': len(seen - set(candidates)),
            'status': 'UNEXPLORED_AVAILABLE' if uncovered else 'BOUNDED_GRAMMAR_EXHAUSTED',
            'recommendation': candidates[uncovered[0]]['workflow_plan'] if uncovered else None,
            'graphs': [candidates[key] for key in sorted(candidates)]}


def report(history_root):
    with no_network() as network:
        observed = observed_graphs(history_root)
        groups = [capacity_group(suite, industry, observed) for suite in SUITES for industry in INDUSTRIES
                  if modules_for(industry, suite)]
    return {'version': VERSION, 'source_sha256': source_tree_hash(ROOT),
            'planner_sha256': sha(Path(__file__)), 'module_version': WORKFLOW_MODULES_VERSION,
            'history_root': str(history_root.resolve()), 'observed_candidates': observed, 'groups': groups,
            'network': network, 'provider_calls': 0, 'new_dev_pairs': 0, 'formal_accepted': False,
            'scope': 'COMPILE_FEASIBLE_BOUNDED_GRAMMAR_NOT_ALL_LEGAL_DAGS_OR_EXECUTED_DIVERSITY',
            'notes': ['Previously compiled includes rejected and quarantined attempts, not just admitted data.',
                      'New typed graph identity is planning guidance, not a guarantee of history-dedup acceptance.',
                      'Unexplored graphs still need runtime witnesses, strict Replay, all-history dedup and semantic review.',
                      'Graph counts are scoped per suite/industry; summing groups does not count unique scientific mechanisms.',
                      'T362 remains SIMULATION_ONLY; actor assignment is the actual suite runtime mapping.']}


def add_observed_coverage(tasks, capacity):
    """Show every attempted graph to planning, without treating it as admitted."""
    groups = {(g['suite'], g['industry']): g for g in capacity['groups']}
    result = []
    for original in tasks:
        task = dict(original)
        covered = {row['family_id']: row for row in task['covered_workflows']}
        group = task['suite'], task['industry']
        for row in capacity['observed_candidates']:
            if (row['suite'], row['industry']) != group or row['family_id'] in covered:
                continue
            binding = read(row['binding_file'])
            assert sha(Path(row['binding_file'])) == row['binding_sha256']
            covered[row['family_id']] = {'family_id': row['family_id'],
                'stages': [{**{key: step[key] for key in ('stage_id', 'module_id', 'requires')},
                            'when': step.get('when')}
                           for step in binding.get('plan', [])],
                'historical_candidate_status': row['candidate_status'],
                'historical_admission': row['admission']}
        task['covered_workflows'] = [covered[key] for key in sorted(covered)]
        task['bounded_workflow_capacity'] = {key: groups[group][key] for key in
            ('status', 'bounded_graph_capacity', 'previously_compiled_in_grammar', 'unexplored_in_grammar')}
        result.append(task)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-root', type=Path, default=ROOT / 'artifacts/v5/data_factory')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = report(args.history_root)
    atomic_json(args.out, result)
    for group in result['groups']:
        print(group['suite'], group['industry'], group['bounded_graph_capacity'],
              group['previously_compiled_in_grammar'], group['unexplored_in_grammar'], flush=True)


if __name__ == '__main__':
    main()
