from ioabench.ioa.reputation import ReputationEvent, ReputationStore


def test_reputation_has_local_and_global_scopes() -> None:
    store = ReputationStore()
    store.record(ReputationEvent("agent-1", 1.0, "local:org-a", "review", {"case": "1"}))
    store.record(ReputationEvent("agent-1", -0.5, "global", "review", {}))
    assert store.value("agent-1", "local:org-a") == 1.0
    assert store.value("agent-1", "global") == -0.5
    assert store.events("agent-1")[0].metadata["case"] == "1"
