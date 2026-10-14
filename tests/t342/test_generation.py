from ioabench.suites.t342.generation import T342Generator, T342_WORLDS
def test_t342_generation() -> None:
    cases = [T342Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T342_WORLDS)]; assert {c.world_id for c in cases} == set(T342_WORLDS); assert all(c.ground_truth.as_dict()["proposition_truth"] is False for c in cases)
