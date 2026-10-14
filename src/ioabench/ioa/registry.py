"""Local visible Agent registry; claims remain separate from hidden truth."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class AgentRecord:
    record_id: str
    agent_id: str
    org_id: str
    role_id: str
    capabilities: frozenset[str]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    claims: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryResult:
    record: AgentRecord
    score: int
    evidence: tuple[str, ...]


class LocalRegistry:
    def __init__(self, telemetry: Callable[[Mapping[str, Any]], None] | None = None) -> None:
        self._records: dict[str, AgentRecord] = {}
        self._telemetry = telemetry

    def publish(self, record: AgentRecord, *, idempotency_key: str) -> AgentRecord:
        existing = self._records.get(record.record_id)
        if existing is not None:
            if existing != record:
                raise ValueError(f"record id already published with different content: {record.record_id}")
            return existing
        self._records[record.record_id] = record
        self._emit({"event_type": "agent.registry.publish", "record_id": record.record_id, "idempotency_key": idempotency_key})
        return record

    def get(self, record_id: str) -> AgentRecord | None:
        return self._records.get(record_id)

    def discover(self, query: Mapping[str, Any]) -> tuple[DiscoveryResult, ...]:
        required = set(query.get("capabilities", ()))
        org_id = query.get("org_id")
        role_id = query.get("role_id")
        results: list[DiscoveryResult] = []
        for record in self._records.values():
            if org_id is not None and record.org_id != org_id:
                continue
            if role_id is not None and record.role_id != role_id:
                continue
            if not required <= record.capabilities:
                continue
            evidence = [f"capability:{capability}" for capability in sorted(required)]
            if org_id is not None:
                evidence.append("org_match")
            if role_id is not None:
                evidence.append("role_match")
            results.append(DiscoveryResult(record, len(evidence), tuple(evidence)))
        results.sort(key=lambda item: (-item.score, item.record.record_id))
        self._emit({
            "event_type": "agent.discovery.result",
            "query": dict(query),
            "record_ids": [item.record.record_id for item in results],
            "evidence": [list(item.evidence) for item in results],
        })
        return tuple(results)

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(record) for record in self._records.values())

    def _emit(self, event: Mapping[str, Any]) -> None:
        if self._telemetry is not None:
            self._telemetry(event)
