from ioabench.suites.t332.spec import build_spec


def test_t332_spec() -> None:
    spec = build_spec()
    assert spec.test_id == "T332" and len(spec.mechanism_families) == 5
    assert spec.minimum_safe_behavior and spec.robust_safe_behavior and spec.unsafe_behavior
