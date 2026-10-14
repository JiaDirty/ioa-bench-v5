from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, NewType, Protocol

RunId = NewType("RunId", str)
ExperimentId = NewType("ExperimentId", str)
CaseId = NewType("CaseId", str)
AgentId = NewType("AgentId", str)
OrganizationId = NewType("OrganizationId", str)
EventId = NewType("EventId", str)

class RunState(str, Enum):
    PENDING: str
    PREPARING: str
    READY: str
    RUNNING: str
    COLLECTING: str
    SCORING: str
    VALIDATING: str
    COMPLETED: str
    RETRYABLE_INFRA_FAILURE: str
    INVALID_RUN: str
    UNSUPPORTED: str
    FAILED: str
    CANCELLED: str

class BehaviorOutcome(str, Enum):
    EARLY_SAFE: str
    LATE_RECOVERY: str
    UNSAFE_ACTION: str
    FULL_FAILURE: str
    TASK_SAFE_BUT_FAILED: str
    INVALID_RUN: str
    UNSUPPORTED: str

@dataclass(frozen=True)
class RunManifest: ...
@dataclass(frozen=True)
class CaseSpec: ...
@dataclass(frozen=True)
class RunPlan: ...
@dataclass(frozen=True)
class ValidationFinding: ...

class RunLifecycle(Protocol):
    async def state(self, run_id: RunId) -> RunState: ...
    async def transition(self, run_id: RunId, to_state: RunState, *, idempotency_key: str, details: Mapping[str, Any] | None = ...) -> None: ...
