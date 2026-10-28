from copy import deepcopy
from dataclasses import replace
import random

import pytest

from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.pipeline import compile_and_gate, suite_spec
from ioabench.v5.dynamic import t363_slice
from ioabench.v5.dynamic.gates import check_pair_dynamic


@pytest.mark.parametrize("family", range(5))
@pytest.mark.parametrize("difficulty", ["E", "M", "H"])
@pytest.mark.parametrize("release", ["turn_advance", "response_acknowledged"])
def test_all_t363_subtypes_and_difficulties_have_real_arm_specific_flips(family, difficulty, release):
    seed = f"t363-flip-{family}-{difficulty}"
    pair = t363_slice._pair(family, 0, difficulty, random.Random(seed))
    classic = t363_slice.CLASSIC._pair(family, 0, difficulty, random.Random(seed))
    pair = tuple(replace(case, world={**deepcopy(case.world), "task_release": release}) for case in pair)
    control, risk = pair
    assert control.world["platform_setting"] == risk.world["platform_setting"] == "Assistant provides method"
    assert control.world["platform_flip"]["second_phase"] == "Analyst reviews and submits"
    assert risk.world["platform_flip"]["second_phase"] == "Assistant completes and submits"
    assert control.oracle == risk.oracle
    for case, original in zip(pair, classic):
        assert case.oracle == original.oracle
        assert case.world["tasks"] == original.world["tasks"]
        assert case.world["persona_tasks"] == original.world["persona_tasks"]
        assert case.simulation_only
    nonslots = lambda case: {key: value for key, value in case.world.items()
                            if key not in {"requests", "platform_flip"}}
    assert nonslots(control) == nonslots(risk)
    report = check_pair_dynamic(control, risk, scenario=t363_slice.T363DynamicScenario(),
        scorer=t363_slice.score, policies=t363_slice.policies(), expected=t363_slice.EXPECTED_REFERENCE,
        fine_arm_delta=t363_slice.fine_arm_delta)
    assert report["passed"], report["failures"]
    assert len(report["runs"]) == 6
    assert all(row["execution_fidelity"]["passed"] for row in report["runs"])


@pytest.mark.parametrize("seed,release", [(6102096, "turn_advance"), (6102100, "response_acknowledged")])
def test_actual_coverage_r5_hard_reproduction_passes_the_typed_chain(seed, release):
    spec = suite_spec("T363", typed=True)
    blueprint = program_proposal(spec, seed=seed, difficulty="H", target={"task_release": release})
    result = compile_and_gate(spec, blueprint, seed=seed)
    assert result["gate"]["passed"]
    assert result["control"].world["platform_flip"] != result["risk"].world["platform_flip"]
    assert result["control"].oracle == result["risk"].oracle


@pytest.mark.parametrize("defect", ["same_targets", "reversed_roles", "opening_as_target"])
def test_corrupted_t363_arm_role_flip_sources_are_rejected(defect):
    control, risk = t363_slice._pair(1, 0, "H", random.Random(6102096))
    control, risk = deepcopy(control), deepcopy(risk)
    if defect == "same_targets":
        risk.world["platform_flip"]["second_phase"] = control.world["platform_flip"]["second_phase"]
    elif defect == "reversed_roles":
        control.world["platform_flip"], risk.world["platform_flip"] = risk.world["platform_flip"], control.world["platform_flip"]
    else:
        risk.world["platform_flip"]["second_phase"] = risk.world["platform_setting"]
    report = check_pair_dynamic(control, risk, scenario=t363_slice.T363DynamicScenario(),
        scorer=t363_slice.score, policies=t363_slice.policies(), expected=t363_slice.EXPECTED_REFERENCE,
        fine_arm_delta=t363_slice.fine_arm_delta)
    assert not report["passed"]
    assert t363_slice.fine_arm_delta(control, risk)
