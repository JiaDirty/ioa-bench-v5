from ioabench.suites.t331.generation import T331Generator, T331_WORLDS


def test_t331_generation_uses_graph_truth_and_worlds() -> None:
    cases = [T331Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T331_WORLDS)]
    assert {case.world_id for case in cases} == set(T331_WORLDS)
    assert all(case.ground_truth.as_dict()["local_error"] is True for case in cases)
