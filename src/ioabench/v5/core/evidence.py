"""Evidence graph for the dynamic IoA world (dynamic-world phase M2, DW-021).

Evidence items are world facts with provenance and a visibility *timeline*: registered (exists
in the world), revealed (an agent channel now carries it), revoked/superseded (no longer
lawful to rely on). The graph is bookkeeping the world and evaluators share: content still
reaches agents only through message/tool channels (the observation firewall path is unchanged);
the graph stamps *when* each item became visible so timing properties ("verified before
acting", "relied on revoked evidence") are decidable from the ledger, not from prose.

Truth layering per 02_RUNTIME_AND_MEASUREMENT_DESIGN §3: the graph holds agent-visible and
evaluator-private views apart — an item marked ``evaluator_private`` is bookkeeping only and
MUST never be delivered to an agent channel.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

EVIDENCE_VERSION = "v5-evidence-graph-1.0.0"
ITEM_STATUSES = ("registered", "revealed", "revoked", "superseded")
AUTHORITIES = ("authoritative", "attested", "self_asserted", "evaluator_private")


@dataclass
class EvidenceItem:
    item_id: str
    content: Any
    source: str
    authority: str = "attested"            # one of AUTHORITIES
    status: str = "registered"             # one of ITEM_STATUSES
    revealed_at_seq: int | None = None
    revealed_to: tuple[str, ...] = ()
    revoked_at_seq: int | None = None
    revocation_reason: str | None = None
    conflicts_with: tuple[str, ...] = ()
    supersedes: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "source": self.source, "authority": self.authority,
                "status": self.status, "revealed_at_seq": self.revealed_at_seq,
                "revealed_to": list(self.revealed_to), "revoked_at_seq": self.revoked_at_seq,
                "revocation_reason": self.revocation_reason, "conflicts_with": list(self.conflicts_with),
                "supersedes": self.supersedes, "meta": deepcopy(dict(self.meta))}


class EvidenceGraph:
    """Timeline-tracked evidence registry. Content delivery stays on message/tool channels."""

    VERSION = EVIDENCE_VERSION

    def __init__(self) -> None:
        self.items: dict[str, EvidenceItem] = {}

    def register(self, item: EvidenceItem) -> EvidenceItem:
        if item.item_id in self.items:
            raise ValueError(f"evidence id already registered: {item.item_id}")
        if item.authority not in AUTHORITIES:
            raise ValueError(f"unknown authority {item.authority!r}")
        if item.supersedes is not None and item.supersedes not in self.items:
            raise ValueError(f"item {item.item_id} supersedes unknown item {item.supersedes}")
        for other in item.conflicts_with:
            if other not in self.items:
                raise ValueError(f"item {item.item_id} conflicts with unknown item {other}")
        self.items[item.item_id] = item
        return item

    def reveal(self, item_id: str, *, seq: int, to: tuple[str, ...] = ()) -> EvidenceItem:
        item = self._get(item_id)
        if item.status in ("revoked", "superseded"):
            raise ValueError(f"cannot reveal {item_id} in status {item.status}")
        if item.authority == "evaluator_private" and to:
            raise ValueError("evaluator_private evidence must never be revealed to agents")
        if item.status != "revealed":
            item.status = "revealed"
            item.revealed_at_seq = seq
        item.revealed_to = tuple(sorted(set(item.revealed_to) | set(to)))
        return item

    def revoke(self, item_id: str, *, seq: int, reason: str) -> EvidenceItem:
        item = self._get(item_id)
        if item.status not in ("revealed", "registered"):
            raise ValueError(f"cannot revoke {item_id} in status {item.status}")
        item.status = "revoked"
        item.revoked_at_seq = seq
        item.revocation_reason = reason
        return item

    def supersede(self, item_id: str, *, seq: int, by: str) -> EvidenceItem:
        item = self._get(item_id)
        if item.status not in ("revealed", "registered"):
            raise ValueError(f"cannot supersede {item_id} in status {item.status}")
        item.status = "superseded"
        item.revoked_at_seq = seq
        item.revocation_reason = f"superseded by {by}"
        return item

    def _get(self, item_id: str) -> EvidenceItem:
        if item_id not in self.items:
            raise KeyError(f"unknown evidence item {item_id}")
        return self.items[item_id]

    def is_visible(self, item_id: str, *, at_seq: int, to: str | None = None) -> bool:
        """Whether the item had been revealed (and not revoked/superseded) at ``at_seq``."""
        item = self._get(item_id)
        if item.revealed_at_seq is None or item.revealed_at_seq > at_seq:
            return False
        if item.revoked_at_seq is not None and item.revoked_at_seq <= at_seq:
            return False
        if to is not None and item.revealed_to and to not in item.revealed_to:
            return False
        return True

    def as_of(self, at_seq: int, *, to: str | None = None) -> list[EvidenceItem]:
        return [item for item in self.items.values()
                if self.is_visible(item.item_id, at_seq=at_seq, to=to)]

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.VERSION, "items": [i.as_dict() for i in self.items.values()]}
