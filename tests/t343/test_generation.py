from ioabench.suites.t343.generation import T343Generator, T343_WORLDS
def test_t343_generation() -> None:
    cases = [T343Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T343_WORLDS)]; assert {c.world_id for c in cases} == set(T343_WORLDS); assert all(c.ground_truth.as_dict()["drift_present"] for c in cases)
