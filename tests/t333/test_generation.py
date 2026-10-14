from ioabench.suites.t333.generation import T333Generator, T333_WORLDS


def test_t333_generation_truth_and_worlds() -> None:
    cases = [T333Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T333_WORLDS)]
    assert {case.world_id for case in cases} == set(T333_WORLDS)
    assert all(case.ground_truth.as_dict()["inference_should_be_qualified"] is True for case in cases)
