from ioabench.ioa.identity import CapabilityEvidence, IdentityClaim, LocalIdentityService


def test_identity_verification_does_not_imply_capability_verification() -> None:
    service = LocalIdentityService({"org-a": "credential-a"})
    service.publish_claim(IdentityClaim("agent-1", "org-a", "analyst", "credential-a", {"claimed": True}))

    identity_only = service.verify("agent-1")
    capability = service.verify("agent-1", "records.write")

    assert identity_only == {"subject_id": "agent-1", "identity_verified": True}
    assert capability["identity_verified"] is True
    assert capability["capability_verified"] is False


def test_capability_evidence_is_explicit_and_independent() -> None:
    service = LocalIdentityService({"org-a": "credential-a"})
    service.publish_claim(IdentityClaim("agent-1", "org-a", "analyst", "bad", {}))
    service.add_capability_evidence(CapabilityEvidence("agent-1", "records.read", True, "training-record"))

    result = service.verify("agent-1", "records.read")

    assert result["identity_verified"] is False
    assert result["capability_verified"] is True
    assert result["capability_evidence_source"] == "training-record"
