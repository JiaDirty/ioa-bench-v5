from ioabench.suites.t332.generation import T332Generator, T332_WORLDS


def test_t332_generation_truth_and_worlds() -> None:
    cases = [T332Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T332_WORLDS)]
    assert {case.world_id for case in cases} == set(T332_WORLDS)
    assert all(case.ground_truth.as_dict()["critical_node_should_remain_hidden"] is True for case in cases)
