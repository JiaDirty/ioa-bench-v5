from ioabench.reports.generate import generate_report


def test_report_marks_simulation_only_and_limitations(tmp_path) -> None:
    path = generate_report({"status_counts": {"VALID": 1}, "suites": {"T361": {"case_count": 1, "valid_count": 1, "task_utility": {"task_success": 1.0}, "validity": "SIMULATION_ONLY"}}}, tmp_path / "report.md", model_id="mock")
    text = path.read_text(encoding="utf-8")
    assert "SIMULATION_ONLY" in text and "real-human" in text
    assert (tmp_path / "tables" / "suite-metrics.csv").exists()
    assert (tmp_path / "risk-profile.json").exists()
    assert (tmp_path / "figures" / "task-utility-by-suite.svg").exists()
