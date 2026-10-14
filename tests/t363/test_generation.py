from ioabench.suites.t363.generation import T363Generator, T363_WORLDS
def test_t363_generation_labels_output() -> None:
    cases = [T363Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T363_WORLDS)]; assert {c.world_id for c in cases} == set(T363_WORLDS); from ioabench.suites.t363.scenario import T363Scenario
    assert T363Scenario("x", "1.0.0", cases[0], ()).document()["simulation_only"] is True
