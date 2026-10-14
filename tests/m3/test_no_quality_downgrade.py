from ioabench.generation.rejection_analysis import summarize_rejections


def test_rejection_analytics_preserves_quality_failure_codes() -> None:
    assert summarize_rejections([
        {"code": "EXPOSURE_REACHABLE", "passed": False},
        {"code": "EXPOSURE_REACHABLE", "passed": False},
        {"code": "CONTROL_SOLVABLE", "passed": True},
    ]) == {"EXPOSURE_REACHABLE": 2}
