"""Branch coverage needs actual paired receipts, not just a planned DAG."""
from copy import deepcopy
import json
from pathlib import Path
import runpy

import pytest

from scripts.v5.workflow_branch_trial import branch_seeds, run_trial
from scripts.v5.verify_development_factory import inventory, no_network
from ioabench.v5.ai_generation.workflow_modules import MODULE_INDEX, conditional_fact_value

HELPERS = runpy.run_path(str(Path(__file__).with_name('test_workflow_composition_r3.py')))
PLAN = HELPERS['MEDICINE_CONDITIONAL']


@pytest.mark.parametrize('start', [0, 7, 14, 869151])
def test_seeds_cover_actual_catalog_facts_without_editing_the_plan(start):
    original = deepcopy(PLAN)
    seeds = branch_seeds(PLAN, start)
    module = MODULE_INDEX['medicine.shortage.check']
    assert len(seeds) == 2 and seeds == branch_seeds(PLAN, start)
    assert {conditional_fact_value(module, seed) for seed in seeds} == {False, True}
    assert PLAN == original


def test_nonconditional_plan_has_no_branch_trials():
    assert branch_seeds(HELPERS['MEDICINE_LINEAR4'], 14) == []


def test_real_branch_matrix_preserves_source_and_resumes_without_execution(tmp_path, monkeypatch):
    from ioabench.v5.ai_generation import direct_deepseek
    target, payload = HELPERS['_SUITES']['T331']
    with no_network() as network:
        row = HELPERS['_run_r3'](tmp_path / 'source', HELPERS['_PlanThenPayloadStudy'](PLAN, payload),
                                  'T331', target, PLAN, assertions=[], seed=14)
        assert row['status'] == 'PASS', row
        source = tmp_path / 'source/candidates/R3-TEST-T331'
        before = inventory(source)
        result = run_trial(source, tmp_path / 'probe')
        assert result['status'] == 'PASS' and result['strict_replays'] == 12
        assert result['new_data_pairs'] == 0 and not result['formal_accepted']
        assert result['observed_branch_values'] == {'s2.shortage': [False, True]}
        assert {tuple(r['executed_stages']) for r in result['witness_runs']} == {
            ('s1', 's2'), ('s1', 's2', 's3', 's4')}
        assert inventory(source) == before
        probe_before = inventory(tmp_path / 'probe')
        monkeypatch.setattr(direct_deepseek, 'strict_checks', lambda *a: pytest.fail('terminal re-executed'))
        assert run_trial(source, tmp_path / 'probe') == result
        assert inventory(tmp_path / 'probe') == probe_before
        replay = next((tmp_path / 'probe').glob('seed-*/REPLAY.json'))
        replay.write_text('[]', encoding='utf-8')
        with pytest.raises(ValueError, match='evidence changed'):
            run_trial(source, tmp_path / 'probe')
        source_case = source / 'PAIR.json'
        source_case.write_text('[]', encoding='utf-8')
        with pytest.raises(ValueError, match='evidence changed'):
            run_trial(source, tmp_path / 'invalid-source')
    assert network['provider_http_or_external_network_attempts'] == 0
