from ioabench.suites.t343.spec import build_spec
def test_t343_spec() -> None:
    spec = build_spec(); assert spec.test_id == "T343" and len(spec.mechanism_families) == 5; assert spec.minimum_safe_behavior and spec.unsafe_behavior
