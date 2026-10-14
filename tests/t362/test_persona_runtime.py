from ioabench.suites.t362.persona_runtime import SyntheticPersonaRuntime
def test_t362_persona_runtime_is_seeded() -> None:
    runtime = SyntheticPersonaRuntime("p2", 8); assert runtime.output("x")["validity"] == "SIMULATION_ONLY"
