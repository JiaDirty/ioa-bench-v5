from ioabench.suites.t321.spec import build_spec

def test_t321_spec() -> None:
    spec = build_spec()
    assert spec.test_id == "T321" and len(spec.mechanism_families) == 5
    assert spec.minimum_safe_behavior and spec.unsafe_behavior
