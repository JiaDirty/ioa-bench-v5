"""Authorization decisions over the SUT-visible delegation graph."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .delegation import Delegation, DelegationGraph


class AuthorizationDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    INDETERMINATE = "INDETERMINATE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AuthorizationResult:
    decision: AuthorizationDecision
    reason: str
    delegation_id: str | None = None


class LocalAuthorizer:
    def __init__(self, graph: DelegationGraph) -> None:
        self.graph = graph

    def authorize(self, *, subject: str, resource: str, action: str, audience: str, delegation_id: str | None) -> AuthorizationResult:
        if delegation_id is None:
            return AuthorizationResult(AuthorizationDecision.INDETERMINATE, "no delegation supplied")
        delegation = self.graph.get(delegation_id)
        if delegation is None:
            return AuthorizationResult(AuthorizationDecision.ERROR, "delegation not found", delegation_id)
        if delegation.subject != subject or delegation.resource != resource:
            return AuthorizationResult(AuthorizationDecision.DENY, "subject or resource mismatch", delegation_id)
        if action not in delegation.action_scope:
            return AuthorizationResult(AuthorizationDecision.DENY, "action outside scope", delegation_id)
        if delegation.audience and audience not in delegation.audience:
            return AuthorizationResult(AuthorizationDecision.DENY, "audience mismatch", delegation_id)
        if not self.graph.validate_visible(delegation)["valid"]:
            return AuthorizationResult(AuthorizationDecision.DENY, "delegation is not currently valid", delegation_id)
        return AuthorizationResult(AuthorizationDecision.ALLOW, "visible delegation permits action", delegation_id)
