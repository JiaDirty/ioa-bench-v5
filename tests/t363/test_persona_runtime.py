from ioabench.suites.t363.persona_runtime import SyntheticPersonaRuntime
def test_t363_persona_runtime_is_seeded() -> None:
    runtime = SyntheticPersonaRuntime("p3", 9); assert runtime.output("x")["validity"] == "SIMULATION_ONLY"
