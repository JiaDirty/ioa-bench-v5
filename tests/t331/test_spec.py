from ioabench.suites.t331.spec import build_spec


def test_t331_spec_freezes_cascade_families() -> None:
    spec = build_spec()
    assert spec.test_id == "T331" and len(spec.mechanism_families) == 5
    assert "peer.message.forward" in spec.exposure_proof_event_types
    assert spec.minimum_safe_behavior and spec.robust_safe_behavior and spec.unsafe_behavior
