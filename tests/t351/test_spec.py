from ioabench.suites.t351.spec import build_spec
def test_t351_spec() -> None:
    spec = build_spec(); assert spec.test_id == "T351" and len(spec.mechanism_families) == 5; assert spec.minimum_safe_behavior and spec.unsafe_behavior
