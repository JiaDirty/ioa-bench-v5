from ioabench.ioa.knowledge import ClaimInstance, KnowledgeStore


def test_claim_provenance_is_preserved() -> None:
    store = KnowledgeStore()
    claim = ClaimInstance("c-1", "fact-1", "agent-1", "Invoice is pending", 0.7, {"source": "message-1"})
    store.publish(claim)
    assert store.search("pending")[0].provenance["source"] == "message-1"
