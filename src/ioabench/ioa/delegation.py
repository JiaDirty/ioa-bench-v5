"""SUT-visible delegation envelopes and bounded parent graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class Delegation:
    delegation_id: str
    parent_id: str | None
    issuer: str
    subject: str
    resource: str
    action_scope: frozenset[str]
    audience: frozenset[str]
    valid_until: str | None
    max_depth: int
    conditions: Mapping[str, Any] = field(default_factory=dict)


class DelegationGraph:
    def __init__(self) -> None:
        self._delegations: dict[str, Delegation] = {}
        self._revoked: set[str] = set()

    def create(self, *, issuer: str, subject: str, resource: str, action_scope: frozenset[str], audience: frozenset[str], valid_until: str | None = None, max_depth: int = 0, parent_id: str | None = None, conditions: Mapping[str, Any] | None = None, delegation_id: str | None = None) -> Delegation:
        if max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        if parent_id is not None:
            parent = self._delegations[parent_id]
            if parent.max_depth <= 0:
                raise ValueError("parent delegation depth is exhausted")
            if not action_scope <= parent.action_scope:
                raise ValueError("child scope exceeds parent scope")
            max_depth = min(max_depth, parent.max_depth - 1)
        delegation = Delegation(delegation_id or str(uuid4()), parent_id, issuer, subject, resource, action_scope, audience, valid_until, max_depth, dict(conditions or {}))
        self._delegations[delegation.delegation_id] = delegation
        return delegation

    def get(self, delegation_id: str) -> Delegation | None:
        return self._delegations.get(delegation_id)

    def revoke(self, delegation_id: str) -> bool:
        if delegation_id not in self._delegations:
            return False
        self._revoked.add(delegation_id)
        return True

    def validate_visible(self, delegation: Delegation, *, now: str | None = None) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc).isoformat()
        valid = (delegation.valid_until is None or current <= delegation.valid_until) and delegation.delegation_id not in self._revoked
        parent_valid = delegation.parent_id is None or delegation.parent_id in self._delegations
        return {"delegation_id": delegation.delegation_id, "valid": valid and parent_valid, "parent_present": parent_valid, "checked_at": current}
