from ioabench.sandbox.services import build_default_services


def test_default_services_cover_six_local_business_domains() -> None:
    services = build_default_services(seed=10)

    assert {service.spec.domain for service in services.values()} == {
        "enterprise", "finance", "research", "logistics", "software-cloud", "knowledge-email",
    }
    result = services["finance.review"].execute("approve", {"key": "case-1"})
    assert result["status"] == "OK"
    assert services["finance.review"].snapshot()["state"]["revision"] == 1


def test_services_are_seeded_and_have_only_synthetic_side_effects() -> None:
    first = build_default_services(seed=20)
    second = build_default_services(seed=20)

    assert first["enterprise.records"].snapshot() == second["enterprise.records"].snapshot()
    first["enterprise.records"].execute("update", {"key": "invoice", "value": {"status": "updated"}})
    assert second["enterprise.records"].snapshot()["state"]["records"] == {}
