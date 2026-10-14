"""Normalized observable event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from ioabench.hashing import canonical_sha256


STAGES = frozenset({"EXPOSURE", "RECOGNITION", "VERIFICATION", "DECISION", "ACTION", "RECOVERY"})


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    run_id: str
    case_id: str
    event_time: str
    stage: str | None
    event_type: str
    actor_agent_id: str | None = None
    target_agent_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    task_id: str | None = None
    message_id: str | None = None
    delegation_id: str | None = None
    claim_id: str | None = None
    action_id: str | None = None
    protocol: str | None = None
    protocol_version: str | None = None
    outcome: str | None = None
    error_class: str | None = None
    payload_sha256: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        case_id: str,
        event_type: str,
        event_time: str | None = None,
        observed_at: str | None = None,
        stage: str | None = None,
        payload: Any = None,
        attributes: Mapping[str, Any] | None = None,
        **fields: str | None,
    ) -> "NormalizedEvent":
        occurred = event_time or _now()
        observed = observed_at or _now()
        metadata = dict(attributes or {})
        metadata["observed_at"] = observed
        if stage is not None and stage not in STAGES:
            raise ValueError(f"unknown event stage: {stage}")
        return cls(
            event_id=str(fields.pop("event_id", None) or uuid4()),
            run_id=run_id,
            case_id=case_id,
            event_time=occurred,
            stage=stage,
            event_type=event_type,
            payload_sha256=canonical_sha256(payload) if payload is not None else None,
            attributes=metadata,
            **fields,
        )

    @property
    def observed_at(self) -> str:
        return str(self.attributes.get("observed_at", self.event_time))

    def as_row(self) -> tuple[Any, ...]:
        import json

        return (
            self.event_id, self.run_id, self.case_id, self.event_time, self.stage, self.event_type,
            self.actor_agent_id, self.target_agent_id, self.trace_id, self.span_id, self.parent_span_id,
            self.task_id, self.message_id, self.delegation_id, self.claim_id, self.action_id,
            self.protocol, self.protocol_version, self.outcome, self.error_class, self.payload_sha256,
            json.dumps(dict(self.attributes), ensure_ascii=False, sort_keys=True),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
