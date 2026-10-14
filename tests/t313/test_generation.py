from ioabench.suites.t313.generation import T313Generator, T313_WORLDS

def test_t313_generation_truth_and_worlds() -> None:
    cases = [T313Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T313_WORLDS)]
    assert {case.world_id for case in cases} == set(T313_WORLDS)
    assert all(case.ground_truth.as_dict()["boundary_valid"] is False for case in cases)
