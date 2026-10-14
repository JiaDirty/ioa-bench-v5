import pytest

from ioabench.generation.dedup import Deduplicator
from ioabench.suites.t312.generation import T312Generator, T312_WORLDS


def test_t312_generator_uses_programmatic_truth_and_three_worlds() -> None:
    generator = T312Generator()
    cases = [generator.generate(mechanism_index=index, world_id=world, seed=index + 1) for index, world in enumerate(T312_WORLDS)]
    assert {case.world_id for case in cases} == set(T312_WORLDS)
    assert all(case.ground_truth.as_dict()["selected_record_is_suitable"] is False for case in cases)
    assert all(case.condition == "RISK" for case in cases)
    with pytest.raises(ValueError):
        generator.generate(world_id="public-internet")


def test_t312_control_and_risk_candidate_ids_are_distinct() -> None:
    generator = T312Generator()
    control = generator.generate(condition="CONTROL")
    risk = generator.generate(condition="RISK")
    assert control.candidate_id != risk.candidate_id
    assert control.naturalize({}).provenance["pair_id"] == risk.naturalize({}).provenance["pair_id"]


def test_t312_formal_visible_payloads_clear_near_duplicate_gate() -> None:
    generator = T312Generator()
    deduplicator = Deduplicator()
    assert all(
        deduplicator.add(
            generator.generate(
                mechanism_index=(seed // 9) % 5,
                world_id=T312_WORLDS[(seed // 3) % len(T312_WORLDS)],
                difficulty=("easy", "medium", "hard")[seed % 3],
                seed=seed + 1,
                condition="RISK",
            ).sut_payload
        )
        for seed in range(90)
    )
