from ioabench.suites.t361.generation import T361Generator, T361_WORLDS
def test_t361_generation_labels_output() -> None:
    cases = [T361Generator().generate(mechanism_index=i, world_id=w, seed=i + 1) for i, w in enumerate(T361_WORLDS)]; assert {c.world_id for c in cases} == set(T361_WORLDS); from ioabench.suites.t361.scenario import T361Scenario
    assert T361Scenario("x", "1.0.0", cases[0], ()).document()["simulation_only"] is True
