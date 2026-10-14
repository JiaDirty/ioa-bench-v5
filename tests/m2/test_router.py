from ioabench.ioa.registry import AgentRecord, LocalRegistry
from ioabench.ioa.router import TaskRouter


def test_router_returns_ranked_candidates_and_visible_rationale() -> None:
    events = []
    registry = LocalRegistry()
    registry.publish(AgentRecord("r-a", "agent-a", "org-a", "analyst", frozenset({"read"})), idempotency_key="a")
    registry.publish(AgentRecord("r-b", "agent-b", "org-b", "analyst", frozenset({"read", "review"})), idempotency_key="b")
    router = TaskRouter(registry, events.append)

    candidates = router.select({"task_id": "task-1", "capabilities": ["read", "review"]})

    assert [item.record.agent_id for item in candidates] == ["agent-b"]
    assert candidates[0].rationale == ("capability:read", "capability:review")
    assert events[-1]["event_type"] == "agent.router.selection"


def test_router_can_be_deterministically_empty() -> None:
    router = TaskRouter(LocalRegistry())
    assert router.choose({"task_id": "task-1", "capabilities": ["missing"]}) is None
