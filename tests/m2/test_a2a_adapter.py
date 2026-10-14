import asyncio

from ioabench.protocols.a2a import LocalA2AAdapter


def test_a2a_discovers_negotiates_sends_and_deduplicates() -> None:
    events = []
    adapter = LocalA2AAdapter(events.append)
    adapter.register("agent-b", {"agent_id": "agent-b", "accepted_types": ["message", "task"]}, lambda envelope: {"received": envelope.payload["text"]})

    card = asyncio.run(adapter.discover_card("agent-b"))
    negotiation = asyncio.run(adapter.negotiate("agent-b", {"types": ["message", "artifact"]}))
    envelope = {"sender_id": "agent-a", "receiver_id": "agent-b", "kind": "message", "payload": {"text": "hello"}}
    result = asyncio.run(adapter.send("agent-b", envelope, idempotency_key="m-1"))
    duplicate = asyncio.run(adapter.send("agent-b", envelope, idempotency_key="m-1"))

    assert card["agent_id"] == "agent-b"
    assert negotiation["accepted_types"] == ["message"]
    assert result == {"received": "hello"}
    assert duplicate["status"] == "DUPLICATE"
    assert {event["event_type"] for event in events} >= {"protocol.negotiation", "agent.message.sent", "agent.message.received"}
