"""Exercise both business-branch outcomes from a retained compositional proposal.

These are local reference probes, never new admissions or a rewrite of the source.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.v5.verify_development_factory import inventory, read, sha
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.aihubmix_study import immutable
from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.ai_generation.tree_factory import business_context, runtime_agent_ids
from ioabench.v5.ai_generation.workflow_compiler import compile_plan
from ioabench.v5.ai_generation.workflow_modules import MODULE_INDEX, conditional_fact_value
from ioabench.v5.evaluation import atomic_json

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'ioabench.v5.workflow-branch-trial/1.0.0'


def branch_seeds(plan, start):
    """Greedily cover both values in the catalog's 14-seed business-fact cycle."""
    modules = {stage['id']: MODULE_INDEX[stage['module']] for stage in plan['stages']}
    sources = {stage['when']['stage'] for stage in plan['stages'] if stage.get('when')}
    covered, seeds = set(), []
    for seed in range(start, start + 14) if sources else ():
        values = {(source, conditional_fact_value(modules[source], seed)) for source in sources}
        if values - covered:
            seeds.append(seed)
            covered |= values
        if len(covered) == 2 * len(sources):
            break
    return seeds


def run_trial(source, out):
    from ioabench.v5.ai_generation.direct_deepseek import candidate_result, strict_checks
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.is_relative_to(source) or source.is_relative_to(out):
        raise ValueError('branch probes must be separate from the retained source')
    candidate_result(source)
    original_files = inventory(source)
    manifest = read(source / 'MANIFEST.json')
    if manifest['route'] != 'compositional_r3':
        raise ValueError('branch probes require a retained compositional proposal')
    task = manifest['task']
    plan = read(source / 'WORKFLOW_PLAN_MODEL_DOC.json')['plan']
    seeds = branch_seeds(plan, int(task['seed']))
    if not seeds:
        raise ValueError('proposal has no conditional business stages')
    contract = {'version': VERSION, 'source_directory': str(source), 'source_files': original_files,
                'runtime_source_sha256': source_tree_hash(ROOT), 'tool_sha256': sha(Path(__file__)),
                'seeds': seeds, 'scope': 'ENGINEERING_BRANCH_COVERAGE_ONLY', 'provider_calls': 0,
                'formal_accepted': False, 'new_data_pairs': 0}
    out.mkdir(parents=True, exist_ok=True)
    immutable(out / 'MANIFEST.json', contract)
    if (out / 'TERMINAL.json').exists():
        terminal = read(out / 'TERMINAL.json')
        if terminal['files'] != inventory(out, except_names=('TERMINAL.json',)):
            raise ValueError('branch trial evidence changed')
        return read(out / 'RESULT.json')
    spec = suite_spec(task['suite'], typed=True)
    blueprint = read(source / 'BLUEPRINT.json')
    original_pair = spec.adapter.compile_pair(blueprint, seed=task['seed'])
    selection = business_context(task)['selection']
    agents = runtime_agent_ids(spec, original_pair[0])
    conditions = {(s['when']['stage'], s['when']['fact']) for s in plan['stages'] if s.get('when')}
    observed = {(stage, fact, arm): set() for stage, fact in conditions for arm in ('CONTROL', 'RISK')}
    witness_runs, replay_count = [], 0
    for seed in seeds:
        directory = out / f'seed-{seed}'
        directory.mkdir(exist_ok=True)
        binding, errors = compile_plan(plan, selection, task['suite'], agents, seed=seed)
        if errors:
            raise CandidateRejected('WORKFLOW_PLAN_INVALID', errors)
        proposal = deepcopy(blueprint)
        proposal['suite_payload']['business_binding'] = binding.as_dict()
        compiled = compile_and_gate(spec, proposal, seed=seed)
        atomic_json(directory / 'BLUEPRINT.json', proposal)
        atomic_json(directory / 'BUSINESS_BINDING.json', binding.as_dict())
        atomic_json(directory / 'PAIR.json', [compiled[a].as_dict() for a in ('control', 'risk')])
        atomic_json(directory / 'HARD_GATE.json', compiled['gate'])
        replay_count += strict_checks(directory, spec, compiled)
        runs = []
        for row in read(directory / 'STRICT_REFERENCE_RESULTS.json'):
            policy = next(p for p in spec.policies if row['run_id'].endswith('-' + p))
            trace = SimpleNamespace(actions=[SimpleNamespace(**a) for a in row['trace']['actions']],
                                    events=row['trace']['events'])
            runs.append({'arm': row['arm'], 'policy': policy, 'trace': trace})
            if policy != 'witness':
                continue
            receipts = {a.result['stage_id']: a.result for a in trace.actions
                        if a.status == 'ok' and (a.result or {}).get('stage_id')}
            readings = {}
            for stage, fact in sorted(conditions):
                actual = receipts.get(stage, {}).get(fact)
                expected = next(s['branch_fact']['value'] for s in binding.plan if s['stage_id'] == stage)
                if type(actual) is not bool or actual != expected:
                    raise CandidateRejected('BRANCH_RECEIPT_MISSING_OR_CHANGED', [stage, fact, row['arm']])
                observed[stage, fact, row['arm']].add(actual)
                readings[stage + '.' + fact] = actual
            witness_runs.append({'seed': seed, 'arm': row['arm'], 'branch_receipts': readings,
                                 'executed_stages': [s['stage_id'] for s in binding.plan if s['stage_id'] in receipts]})
        claims = business_witnesses(binding, runs)
        atomic_json(directory / 'BUSINESS_WITNESSES.json', claims)
        if not claims or any(c['status'] == 'DESIGN_EXECUTION_FIDELITY_FAIL' for c in claims):
            raise CandidateRejected('BUSINESS_BRANCH_FIDELITY', claims)
    if any(values != {False, True} for values in observed.values()):
        raise CandidateRejected('BRANCH_COVERAGE_INCOMPLETE', [str(key) for key, values in observed.items()
                                                             if values != {False, True}])
    if inventory(source) != original_files:
        raise ValueError('retained source changed during branch trial')
    result = {'version': VERSION, 'status': 'PASS', 'scope': contract['scope'],
              'observed_branch_values': {stage + '.' + fact: [False, True] for stage, fact in sorted(conditions)},
              'witness_runs': witness_runs, 'strict_replays': replay_count,
              'provider_calls': 0, 'formal_accepted': False, 'new_data_pairs': 0,
              'original_admission_unchanged': True}
    atomic_json(out / 'RESULT.json', result)
    atomic_json(out / 'TERMINAL.json', {'files': inventory(out, except_names=('TERMINAL.json',))})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = run_trial(args.source, args.out)
    print(json.dumps({key: result[key] for key in ('status', 'scope', 'strict_replays', 'provider_calls')}))


if __name__ == '__main__':
    main()
