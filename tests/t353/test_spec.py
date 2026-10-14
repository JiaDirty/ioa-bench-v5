from ioabench.suites.t353.spec import build_spec
def test_t353_spec() -> None:
    spec = build_spec(); assert spec.test_id == "T353" and len(spec.mechanism_families) == 5; assert spec.minimum_safe_behavior and spec.unsafe_behavior
