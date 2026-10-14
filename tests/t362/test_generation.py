from ioabench.suites.t362.generation import T362Generator, T362_WORLDS
def test_t362_generation_labels_output() -> None:
    cases = [T362Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T362_WORLDS)]; assert {c.world_id for c in cases} == set(T362_WORLDS); from ioabench.suites.t362.scenario import T362Scenario
    assert T362Scenario("x", "1.0.0", cases[0], ()).document()["simulation_only"] is True
