from ioabench.ioa.memory import AgentMemory


def test_memory_isolated_and_resettable() -> None:
    first = AgentMemory()
    second = AgentMemory()
    first.put("answer", {"value": 1})
    second.put("answer", {"value": 2})
    first.reset()
    assert first.get("answer") is None
    assert second.get("answer") == {"value": 2}
