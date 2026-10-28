"""Deterministic admission facts precede semantic judgment in review protocol 2."""
from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.audit_facts import (
    REQUIRED_ACCEPT_FACT_KEYS, blocking_fact_errors, evidence_summary)

REPLAY_FIELDS = {"actions", "events", "exposure", "final_state", "monitors", "outcome",
                 "score", "status", "all_responses_consumed"}


def preflight(packet, facts):
    from ioabench.v5.ai_generation.development_audit import PROTOCOL_V21, PROTOCOL_V22, PROTOCOL_V23, PROTOCOL_V24, GROUPED_CITATION_PROTOCOLS, evidence_path, prepare_audit_packet
    errors = [*packet["hard_gate_errors"], *blocking_fact_errors(facts)]
    errors.extend("UNESTABLISHED_FACT:" + key for key in REQUIRED_ACCEPT_FACT_KEYS if facts.get(key) is None)
    if facts.get("design_assertion_count", 0) and facts.get("design_assertions_verified") is not True:
        errors.append("DESIGN_NOT_CONSUMED")
    documents = packet["documents"]
    summary = evidence_summary(documents)
    if any(documents["facts_summary"].get(key) != value for key, value in summary.items()):
        errors.append("FACT_SUMMARY_CONTRADICTION")
    if packet["version"] in {PROTOCOL_V21, PROTOCOL_V22, *GROUPED_CITATION_PROTOCOLS}:
        from ioabench.v5.ai_generation.audit_facts import execution_accounting
        if documents["facts_summary"].get("execution_accounting") != execution_accounting(documents):
            errors.append("EXECUTION_ACCOUNTING_CONTRADICTION")
    if packet["version"] in {PROTOCOL_V22, *GROUPED_CITATION_PROTOCOLS}:
        from ioabench.v5.ai_generation.audit_facts import action_accounting
        if documents["facts_summary"].get("action_accounting") != action_accounting(documents):
            errors.append("ACTION_ACCOUNTING_CONTRADICTION")
    expected = 2 * packet["configured_reference_policies"]
    if len(documents["replay"]) != expected or len(documents["execution"]["runs"]) != expected:
        errors.append("STRICT_REPLAY_CONFIGURED_MATRIX_INCOMPLETE")
    if any(not REPLAY_FIELDS <= set(row.get("checks", {})) for row in documents["replay"]):
        errors.append("STRICT_REPLAY_CHECKS_INCOMPLETE")
    if not errors:
        original = prepare_audit_packet(evidence_path(packet["source_binding"]["directory"]),
                                       protocol=packet["version"])
        if canonical_sha256(original) != canonical_sha256(packet):
            errors.append("PACKET_SOURCE_MISMATCH")
    return {"version": "ioabench.v5.audit-preflight/1.4.0" if packet["version"] == PROTOCOL_V24 else "ioabench.v5.audit-preflight/1.3.0" if packet["version"] == PROTOCOL_V23 else "ioabench.v5.audit-preflight/1.2.0" if packet["version"] == PROTOCOL_V22 else "ioabench.v5.audit-preflight/1.1.0" if packet["version"] == PROTOCOL_V21 else "ioabench.v5.audit-preflight/1.0.0", "status": "REJECTED" if errors else "PASS",
            "errors": list(dict.fromkeys(errors)), "facts": facts,
            "packet_sha256": canonical_sha256(packet), "model_verdict_substituted": False}
