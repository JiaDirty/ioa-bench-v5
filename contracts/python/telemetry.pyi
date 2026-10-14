from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    run_id: str
    case_id: str
    event_time: str
    stage: str | None
    event_type: str
    actor_agent_id: str | None
    target_agent_id: str | None
    trace_id: str | None
    span_id: str | None
    parent_span_id: str | None
    outcome: str | None
    attributes: Mapping[str, Any]
