from ioabench.suites.t352.spec import build_spec
def test_t352_spec() -> None:
    spec = build_spec(); assert spec.test_id == "T352" and len(spec.mechanism_families) == 5; assert spec.minimum_safe_behavior and spec.unsafe_behavior
