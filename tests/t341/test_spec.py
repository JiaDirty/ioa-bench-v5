from ioabench.suites.t341.spec import build_spec
def test_t341_spec() -> None:
    spec = build_spec(); assert spec.test_id == "T341" and len(spec.mechanism_families) == 5; assert spec.minimum_safe_behavior and spec.unsafe_behavior
