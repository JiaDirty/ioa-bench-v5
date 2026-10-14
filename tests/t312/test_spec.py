from ioabench.suites.t312.spec import build_spec


def test_t312_spec_freezes_mechanisms_and_observable_rules() -> None:
    spec = build_spec()
    assert spec.test_id == "T312"
    assert len(spec.mechanism_families) == 5
    assert "registry.crosscheck" in spec.exposure_proof_event_types
    assert spec.minimum_safe_behavior and spec.robust_safe_behavior and spec.unsafe_behavior
    assert "task_success" in spec.utility_metrics
    assert "distorted registry" in spec.control_semantics
