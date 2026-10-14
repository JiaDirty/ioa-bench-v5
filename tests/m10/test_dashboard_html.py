from ioabench.api.dashboard import dashboard_html


def test_dashboard_html_keeps_suites_and_simulation_label() -> None:
    payload = {"run_id": "mock-v1", "categories": {category: {suite: {"case_count": 1} for suite in suites} for category, suites in {
        "trust_authorization": ("T311", "T312", "T313"),
        "protocol_interop": ("T321", "T322", "T323"),
        "propagation_inference": ("T331", "T332", "T333"),
        "public_knowledge": ("T341", "T342", "T343"),
        "ecosystem_power": ("T351", "T352", "T353"),
        "human_agency_simulation": ("T361", "T362", "T363"),
    }.items()}, "status_counts": {}}
    html = dashboard_html(payload)
    assert "T311" in html and "T363" in html and "SIMULATION_ONLY" in html
    assert "No overall 18-suite score" in html
