from copy import deepcopy
from dataclasses import replace

import pytest

from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.bounded_compiler import FACTORS, BoundedWorldCompiler
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec


@pytest.mark.parametrize("suite", FACTORS)
def test_bounded_factors_compile_real_seed_bound_worlds_and_reject_undeclared_truth(suite):
    spec = suite_spec(suite, typed=True)
    field, values, _ = FACTORS[suite]
    assert isinstance(spec.adapter, BoundedWorldCompiler)
    for value in values:
        blueprint = program_proposal(spec, seed=317, difficulty="M", target={field: value})
        result = compile_and_gate(spec, blueprint, seed=317)
        assert result["gate"]["passed"]
        assert all(row["execution_fidelity"]["passed"] for row in result["gate"]["runs"])
        baseline = spec.adapter.base.compile_pair({key: val for key, val in blueprint.items() if key != "suite_payload"}, seed=317)
        assert [result[arm].oracle for arm in ("control", "risk")] == [case.oracle for case in baseline]
        assert result["control"].world[field] == result["risk"].world[field] == value
        assert result["control"].as_dict() == spec.adapter.compile_pair(blueprint, seed=317)[0].as_dict()
    bad = deepcopy(blueprint)
    bad["suite_payload"]["oracle"] = {"safe": True}
    with pytest.raises(CandidateRejected, match="BLUEPRINT_OR_FIDELITY"):
        compile_and_gate(spec, bad, seed=317)


def test_bounded_adapter_cannot_pass_with_missing_actual_field_consumer():
    spec = suite_spec("T361", typed=True)
    blueprint = program_proposal(spec, seed=317, difficulty="M")
    with pytest.raises(CandidateRejected, match="CAPABILITY_GAP"):
        compile_and_gate(replace(spec, scenario_factory=lambda: object()), blueprint, seed=317)
