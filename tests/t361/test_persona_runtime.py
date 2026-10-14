from ioabench.suites.t361.persona_runtime import SyntheticPersonaRuntime
def test_t361_persona_runtime_is_seeded_and_resettable() -> None:
    runtime = SyntheticPersonaRuntime("p1", 7); assert runtime.output("x")["validity"] == "SIMULATION_ONLY"; runtime.advance("withdrawal"); assert runtime.reset()["phase"] == "baseline"
