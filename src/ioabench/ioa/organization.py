"""Organizations, trust domains and explicit cross-domain relationships."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TrustDomain:
    domain_id: str
    name: str


@dataclass(frozen=True)
class Organization:
    org_id: str
    trust_domain_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainRelationship:
    source_org_id: str
    target_org_id: str
    relationship: str
    evidence: dict[str, Any] = field(default_factory=dict)


class OrganizationDirectory:
    def __init__(self) -> None:
        self._domains: dict[str, TrustDomain] = {}
        self._organizations: dict[str, Organization] = {}
        self._relationships: list[DomainRelationship] = []

    def add_domain(self, domain: TrustDomain) -> None:
        if domain.domain_id in self._domains:
            raise ValueError(f"trust domain already exists: {domain.domain_id}")
        self._domains[domain.domain_id] = domain

    def add_organization(self, organization: Organization) -> None:
        if organization.org_id in self._organizations:
            raise ValueError(f"organization already exists: {organization.org_id}")
        if organization.trust_domain_id not in self._domains:
            raise KeyError(organization.trust_domain_id)
        self._organizations[organization.org_id] = organization

    def relate(self, relationship: DomainRelationship) -> None:
        if relationship.source_org_id not in self._organizations or relationship.target_org_id not in self._organizations:
            raise KeyError("relationship references an unknown organization")
        self._relationships.append(relationship)

    def organization(self, org_id: str) -> Organization:
        return self._organizations[org_id]

    def relationships(self, org_id: str | None = None) -> tuple[DomainRelationship, ...]:
        if org_id is None:
            return tuple(self._relationships)
        return tuple(item for item in self._relationships if org_id in {item.source_org_id, item.target_org_id})

    def snapshot(self) -> dict[str, Any]:
        return {
            "domains": [asdict(item) for item in self._domains.values()],
            "organizations": [asdict(item) for item in self._organizations.values()],
            "relationships": [asdict(item) for item in self._relationships],
        }
