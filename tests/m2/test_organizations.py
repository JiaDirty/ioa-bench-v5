from ioabench.ioa.organization import DomainRelationship, Organization, OrganizationDirectory, TrustDomain


def test_cross_domain_relationships_are_queryable_and_replayable() -> None:
    directory = OrganizationDirectory()
    directory.add_domain(TrustDomain("domain-a", "Domain A"))
    directory.add_domain(TrustDomain("domain-b", "Domain B"))
    directory.add_organization(Organization("org-a", "domain-a", "Organization A"))
    directory.add_organization(Organization("org-b", "domain-b", "Organization B"))
    directory.relate(DomainRelationship("org-a", "org-b", "service-partner", {"source": "scenario"}))

    relationships = directory.relationships("org-a")
    snapshot = directory.snapshot()

    assert relationships[0].target_org_id == "org-b"
    assert snapshot["relationships"][0]["relationship"] == "service-partner"
    assert directory.organization("org-a").trust_domain_id != directory.organization("org-b").trust_domain_id
