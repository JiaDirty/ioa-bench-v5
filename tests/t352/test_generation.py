from ioabench.suites.t352.generation import T352Generator, T352_WORLDS
def test_t352_generation() -> None:
    cases = [T352Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T352_WORLDS)]; assert {c.world_id for c in cases} == set(T352_WORLDS); assert all(c.ground_truth.as_dict()["concentration_risk"] for c in cases)
