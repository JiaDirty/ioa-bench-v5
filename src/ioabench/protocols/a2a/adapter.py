"""Small local A2A-like task/message adapter behind a protocol boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping
from uuid import uuid4


class A2AStatus(StrEnum):
    TASK = "task"
    MESSAGE = "message"
    ARTIFACT = "artifact"
    STATUS = "status"


@dataclass(frozen=True)
class A2AEnvelope:
    envelope_id: str
    sender_id: str
    receiver_id: str
    kind: A2AStatus
    payload: Mapping[str, Any]
    protocol: str = "a2a"
    protocol_version: str = "local-v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)


class LocalA2AAdapter:
    def __init__(self, telemetry: Callable[[Mapping[str, Any]], None] | None = None) -> None:
        self._cards: dict[str, Mapping[str, Any]] = {}
        self._handlers: dict[str, Callable[[A2AEnvelope], Mapping[str, Any]]] = {}
        self._seen_keys: set[str] = set()
        self._telemetry = telemetry

    def register(self, endpoint: str, card: Mapping[str, Any], handler: Callable[[A2AEnvelope], Mapping[str, Any]]) -> None:
        self._cards[endpoint] = dict(card)
        self._handlers[endpoint] = handler

    async def discover_card(self, endpoint: str) -> Mapping[str, Any]:
        return dict(self._cards[endpoint])

    async def negotiate(self, endpoint: str, offer: Mapping[str, Any]) -> Mapping[str, Any]:
        card = self._cards[endpoint]
        accepted = set(offer.get("types", ())) & set(card.get("accepted_types", ()))
        result = {"endpoint": endpoint, "accepted_types": sorted(accepted), "protocol": "a2a", "protocol_version": "local-v1"}
        self._emit({"event_type": "protocol.negotiation", **result})
        return result

    async def send(self, endpoint: str, envelope: Mapping[str, Any], *, idempotency_key: str | None = None) -> Mapping[str, Any]:
        key = idempotency_key or str(uuid4())
        if key in self._seen_keys:
            return {"status": "DUPLICATE", "idempotency_key": key}
        self._seen_keys.add(key)
        message = A2AEnvelope(
            envelope_id=str(envelope.get("envelope_id") or uuid4()),
            sender_id=str(envelope["sender_id"]),
            receiver_id=str(envelope["receiver_id"]),
            kind=A2AStatus(envelope["kind"]),
            payload=dict(envelope.get("payload", {})),
            metadata={"idempotency_key": key},
        )
        self._emit({"event_type": "agent.message.sent", "envelope_id": message.envelope_id, "protocol": message.protocol, "protocol_version": message.protocol_version, "sender_id": message.sender_id, "receiver_id": message.receiver_id})
        result = dict(self._handlers[endpoint](message))
        self._emit({"event_type": "agent.message.received", "envelope_id": message.envelope_id, "endpoint": endpoint, "result": result})
        return result

    def _emit(self, event: Mapping[str, Any]) -> None:
        if self._telemetry is not None:
            self._telemetry(event)
