from ioabench.suites.t323.generation import T323Generator, T323_WORLDS

def test_t323_generation_truth_and_worlds() -> None:
    cases = [T323Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T323_WORLDS)]
    assert {case.world_id for case in cases} == set(T323_WORLDS)
    assert all(case.ground_truth.as_dict()["provenance_complete"] is False for case in cases)
