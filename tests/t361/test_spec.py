from ioabench.suites.t361.spec import build_spec
def test_t361_spec_is_simulation_only() -> None:
    spec = build_spec(); assert spec.test_id == "T361" and spec.validity == "SIMULATION_ONLY" and len(spec.mechanism_families) == 5
