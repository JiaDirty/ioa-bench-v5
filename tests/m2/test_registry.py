from ioabench.ioa.registry import AgentRecord, LocalRegistry


def test_registry_discovers_visible_claims_with_rank_evidence_and_telemetry() -> None:
    events = []
    registry = LocalRegistry(events.append)
    registry.publish(AgentRecord("r-1", "agent-1", "org-a", "analyst", frozenset({"records.read", "evidence.review"}), claims={"qualified": True}), idempotency_key="p-1")
    registry.publish(AgentRecord("r-2", "agent-2", "org-b", "analyst", frozenset({"records.read"})), idempotency_key="p-2")

    result = registry.discover({"capabilities": ["records.read", "evidence.review"]})

    assert [item.record.record_id for item in result] == ["r-1"]
    assert result[0].evidence == ("capability:evidence.review", "capability:records.read")
    assert events[-1]["event_type"] == "agent.discovery.result"
    assert registry.get("r-1").claims["qualified"] is True


def test_registry_does_not_expose_oracle_truth_channel() -> None:
    registry = LocalRegistry()
    record = AgentRecord("r-1", "agent-1", "org-a", "analyst", frozenset(), claims={"qualified": False})
    registry.publish(record, idempotency_key="p-1")

    assert "oracle" not in registry.__dict__
    assert registry.get("r-1") == record
