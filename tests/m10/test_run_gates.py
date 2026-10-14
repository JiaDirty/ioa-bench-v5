from ioabench.runtime.run_gates import evaluate_run


def test_run_gate_excludes_missing_exposure_and_infra_failure() -> None:
    assert evaluate_run({"status": "COMPLETED", "telemetry_complete": True}).status == "INVALID_RUN"
    assert not evaluate_run({"status": "RETRYABLE_INFRA_FAILURE"}).eligible_for_safety
    assert evaluate_run({"status": "COMPLETED", "exposure_proven": True, "telemetry_complete": True}).eligible_for_safety
