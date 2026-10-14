from ioabench.suites.t322.generation import T322Generator, T322_WORLDS

def test_t322_generation_truth_and_worlds() -> None:
    cases = [T322Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T322_WORLDS)]
    assert {case.world_id for case in cases} == set(T322_WORLDS)
    assert all(case.ground_truth.as_dict()["semantic_mapping_valid"] is False for case in cases)
