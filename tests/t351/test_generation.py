from ioabench.suites.t351.generation import T351Generator, T351_WORLDS
def test_t351_generation() -> None:
    cases = [T351Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T351_WORLDS)]; assert {c.world_id for c in cases} == set(T351_WORLDS); assert all(c.ground_truth.as_dict()["reward_conflict"] for c in cases)
