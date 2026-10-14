from ioabench.suites.t341.generation import T341Generator, T341_WORLDS
def test_t341_generation() -> None:
    cases = [T341Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T341_WORLDS)]; assert {c.world_id for c in cases} == set(T341_WORLDS); assert all(c.ground_truth.as_dict()["false_consensus"] for c in cases)
