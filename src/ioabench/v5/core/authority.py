"""Authority ledger for the dynamic IoA world (dynamic-world phase M2, DW-021).

Grants are first-class world facts: a subject may perform an action on a resource pattern for
an audience within a validity window, derived from a parent grant. The ledger answers
authorization questions deterministically at action time and records which grant chain
supported a decision — the model-visible form of "who may do what" (ADR principle: authorization
decisions must be checkable against explicit records, not vibes).

Deliberately minimal: no roles/RBAC framework, no crypto, no policy DSL. Suites keep their own
policy text; this component is for worlds whose *executable* permission structure must be
checked and audited (T311 qualification records, T313 delegation graphs, T321 exceptions,
T323 accountability, T342 register confirmations all reduce to grants + validity + derivation).
"""
from __future__ import annotations

import fnmatch
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

AUTHORITY_VERSION = "v5-authority-ledger-1.0.0"


@dataclass(frozen=True)
class Grant:
    grant_id: str
    subject: str                     # agent id or role the grant is issued to
    action: str                      # action/tool-scope token (glob pattern allowed)
    resource: str                    # resource pattern (glob pattern allowed)
    audience: str | None = None      # optional recipient/counterparty constraint
    valid_from: int | None = None    # logical clock turn (inclusive)
    valid_until: int | None = None   # logical clock turn (inclusive); None = no expiry
    derived_from: str | None = None  # parent grant id this grant derives its authority from
    issued_by: str = "environment"
    meta: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"grant_id": self.grant_id, "subject": self.subject, "action": self.action,
                "resource": self.resource, "audience": self.audience, "valid_from": self.valid_from,
                "valid_until": self.valid_until, "derived_from": self.derived_from,
                "issued_by": self.issued_by, "meta": deepcopy(dict(self.meta))}


@dataclass(frozen=True)
class AuthorityDecision:
    granted: bool
    grant_id: str | None
    chain: tuple[str, ...]           # derivation chain from root to the supporting grant
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"granted": self.granted, "grant_id": self.grant_id, "chain": list(self.chain),
                "reason": self.reason}


class AuthorityLedger:
    """Append-only grant ledger with derivation-checked lookups."""

    VERSION = AUTHORITY_VERSION

    def __init__(self) -> None:
        self.grants: dict[str, Grant] = {}
        self.revoked: set[str] = set()

    def issue(self, grant: Grant) -> Grant:
        if grant.grant_id in self.grants:
            raise ValueError(f"grant id already issued: {grant.grant_id}")
        if grant.derived_from is not None and grant.derived_from not in self.grants:
            raise ValueError(f"grant {grant.grant_id} derives from unknown grant {grant.derived_from}")
        self.grants[grant.grant_id] = grant
        return grant

    def revoke(self, grant_id: str) -> None:
        if grant_id not in self.grants:
            raise ValueError(f"unknown grant {grant_id}")
        self.revoked.add(grant_id)

    def _chain_valid(self, grant: Grant, *, at_turn: int | None) -> tuple[bool, str, tuple[str, ...]]:
        """Walk the derivation chain root->grant; every link must be unrevoked, in-window (fail
        closed: a link with a validity window REQUIRES an at_turn to verify against) and each
        link's scope must cover the next link's scope."""
        chain: list[Grant] = []
        current: Grant | None = grant
        while current is not None:
            chain.append(current)
            current = self.grants.get(current.derived_from) if current.derived_from else None
        chain.reverse()  # root first
        for link in chain:
            if link.grant_id in self.revoked:
                return False, f"grant {link.grant_id} in the derivation chain is revoked", ()
            if link.valid_from is not None or link.valid_until is not None:
                if at_turn is None:
                    # fail closed: the grant is time-constrained but the caller cannot prove
                    # the logical time — the constraint cannot be verified
                    return False, (f"grant {link.grant_id} is time-constrained and no logical "
                                   "time was supplied (fail closed)"), ()
                if link.valid_from is not None and at_turn < link.valid_from:
                    return False, f"grant {link.grant_id} not yet valid at turn {at_turn}", ()
                if link.valid_until is not None and at_turn > link.valid_until:
                    return False, f"grant {link.grant_id} expired at turn {at_turn}", ()
        # scope containment: every non-root link must be covered by its parent
        for parent, child in zip(chain, chain[1:]):
            if not (fnmatch.fnmatchcase(child.action, parent.action)
                    and fnmatch.fnmatchcase(child.resource, parent.resource)
                    and (parent.audience is None or child.audience == parent.audience)):
                return False, (f"grant {child.grant_id} ({child.action}/{child.resource}) exceeds "
                               f"parent {parent.grant_id} ({parent.action}/{parent.resource})"), ()
        return True, "chain valid", tuple(g.grant_id for g in chain)

    def check(self, *, actor: str, action: str, resource: str, audience: str | None = None,
              at_turn: int | None = None) -> AuthorityDecision:
        """Whether ``actor`` may perform ``action`` on ``resource`` for ``audience``.

        Fail-closed rules (post-audit AUTH-01):
        * a grant with an ``audience`` constraint only matches when the caller supplies the
          audience being targeted; an absent audience cannot verify the constraint;
        * a grant with a validity window only matches when the caller supplies ``at_turn``.
        """
        best: AuthorityDecision | None = None
        for grant in self.grants.values():
            if grant.subject not in (actor, "*"):
                continue
            if not fnmatch.fnmatchcase(action, grant.action):
                continue
            if not fnmatch.fnmatchcase(resource, grant.resource):
                continue
            if grant.audience is not None:
                if audience is None:
                    # fail closed: the grant constrains the audience but the caller cannot
                    # prove which audience the action targets
                    continue
                if grant.audience != audience:
                    continue
            ok, reason, chain = self._chain_valid(grant, at_turn=at_turn)
            decision = AuthorityDecision(ok, grant.grant_id if ok else None, chain, reason)
            if ok:
                return decision
            best = best or decision
        return best or AuthorityDecision(False, None, (), f"no grant covers {actor}/{action}/{resource}")

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.VERSION,
                "grants": [g.as_dict() for g in self.grants.values()],
                "revoked": sorted(self.revoked)}
