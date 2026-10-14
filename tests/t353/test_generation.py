from ioabench.suites.t353.generation import T353Generator, T353_WORLDS
def test_t353_generation() -> None:
    cases = [T353Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T353_WORLDS)]; assert {c.world_id for c in cases} == set(T353_WORLDS); assert all(c.ground_truth.as_dict()["steering_present"] for c in cases)
