from ioabench.suites.t333.spec import build_spec


def test_t333_spec() -> None:
    spec = build_spec()
    assert spec.test_id == "T333" and len(spec.mechanism_families) == 5
    assert spec.minimum_safe_behavior and spec.robust_safe_behavior and spec.unsafe_behavior
