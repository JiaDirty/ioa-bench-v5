from ioabench.suites.t311.spec import build_spec


def test_t311_spec_freezes_mechanisms_and_observable_rules() -> None:
    spec = build_spec()
    assert spec.test_id == "T311"
    assert len(spec.mechanism_families) == 5
    assert "agent.identity.verify" in spec.exposure_proof_event_types
    assert spec.minimum_safe_behavior and spec.robust_safe_behavior and spec.unsafe_behavior
    assert "task_success" in spec.utility_metrics
    assert "spoofed claim corrected" in spec.control_semantics
