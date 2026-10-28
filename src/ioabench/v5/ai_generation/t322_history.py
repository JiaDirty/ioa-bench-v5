"""Read-only T322 history scoping; incomplete legacy contracts never prove novelty."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Iterable, Mapping

from ioabench.hashing import canonical_sha256
from .history import HISTORY_VERSION
from .quality import QUALITY_VERSION

VERSION = "ioabench.v5.t322-history-scope/1.0.0"
QUARANTINE = "QUARANTINED_HISTORY_INDETERMINATE"


def version_scoped_index(index: Mapping[str, Any], *, target_version: str = "5.1.2"):
    """Retain current-runtime projections for development, preserving every source binding.

    The caller must retain the returned report and quarantine every resulting candidate;
    this view is not an alternative all-history admission gate.
    """
    if target_version != "5.1.2":
        raise ValueError("only the inspected current 5.1.2 base contract is supported")
    if index.get("index_version") != HISTORY_VERSION or index.get("feature_version") != QUALITY_VERSION:
        raise ValueError("rebuild the historical index with the current projection contract")
    scoped = deepcopy(dict(index))
    excluded = [row for row in scoped["records"]
                if row["features"]["suite_id"].split("-")[0] == "T322"
                and row["features"].get("runtime_verified") is not True]
    excluded_hashes = {row["case_sha256"] for row in excluded}
    scoped["records"] = [row for row in scoped["records"] if row["case_sha256"] not in excluded_hashes]
    excluded_findings = [row for row in scoped["findings"] if row.get("suite_id", "").split("-")[0] == "T322"
                         and row.get("code") == "RUNTIME_PROJECTION_UNAVAILABLE"]
    scoped["findings"] = [row for row in scoped["findings"] if row not in excluded_findings]
    report = {"version": VERSION, "scope": "VERSION_SCOPED", "target_base_contract": target_version,
              "full_history_index_sha256": canonical_sha256(index),
              "projection_source_sha256": index["projection_source_sha256"],
              "source_bindings_preserved": True, "global_novelty_proven": False,
              "required_pool_status": QUARANTINE, "dev_accepted_allowed": False,
              "excluded_cases": [{"case_sha256": row["case_sha256"], "occurrences": row["occurrences"],
                                  "reason": "RUNTIME_PROJECTION_UNAVAILABLE; original contract not recovered"}
                                 for row in excluded],
              "excluded_findings": excluded_findings,
              "retained_t322_cases": sum(row["features"]["suite_id"].split("-")[0] == "T322"
                                         for row in scoped["records"]),
              "limitation": "Current-runtime comparability only. Missing legacy facts were not reconstructed; "
                            "nonmatching public fields cannot establish global historical uniqueness."}
    scoped["scope"]["t322_development_scope"] = {key: report[key] for key in (
        "version", "scope", "target_base_contract", "full_history_index_sha256", "required_pool_status",
        "global_novelty_proven", "dev_accepted_allowed")}
    scoped["summary"]["version_scoped_excluded_cases"] = len(excluded)
    scoped["summary"]["unique_cases"] = len(scoped["records"])
    scoped["summary"]["occurrences"] = sum(len(row["occurrences"]) for row in scoped["records"])
    scoped["summary"]["occurrence_statuses"] = dict(Counter(item.get("status", "UNKNOWN")
        for row in scoped["records"] for item in row["occurrences"]))
    return scoped, report


def common_field_fingerprint(case: Any) -> dict[str, Any]:
    """Fingerprint observed public causal fields only; equality can reject, not accept."""
    raw = case.as_dict() if hasattr(case, "as_dict") else case
    if raw["suite_id"].split("-")[0] != "T322":
        raise ValueError("T322 history comparison requires a T322 case")
    world = raw["world"]
    if "instructions" in world:
        primary = next(item for item in world["instructions"]
                       if item["instruction_id"] == world["primary_instruction_id"])
        kind = "static_primary_record"
    elif "native_ledger" in world and "gateway" in world:
        primary, kind = world, "static_primary_record"
    elif "native_pre" in world and "native_transition" in world:
        # A pre-transition dynamic record is not equivalent to a static record.
        primary, kind = None, "dynamic_native_transition"
    else:
        raise ValueError("observed T322 world lacks a supported public record shape")
    if primary is not None:
        fields = {"requested_action": primary["requested_action"],
                  "native_ledger": {name: primary["native_ledger"][name] for name in
                                    ("state", "applied", "valid", "effect_count") if name in primary["native_ledger"]},
                  "gateway": {name: primary["gateway"][name] for name in
                              ("status_code", "idempotency_key_present", "cancellation", "validity_unit",
                               "validity_value", "destination_code", "mapped_code", "retry_number")
                              if name in primary["gateway"]}}
    else:
        native = ("state", "applied", "native_effect")
        transition = world["native_transition"]
        fields = {"requested_action": world["instruction"]["requested_action"],
                  "gateway_status": world["gateway_status"],
                  "native_pre": {name: world["native_pre"][name] for name in native if name in world["native_pre"]},
                  "native_transition": {"mode": transition["mode"], "resulting_native": {
                      name: transition["resulting_native"][name] for name in native if name in transition["resulting_native"]}},
                  "native_record_access": world.get("native_record_access", "direct")}
    projection = {"fingerprint_version": VERSION, "suite_id": "T322", "arm": raw["arm"],
                  "subtype": raw["subtype"], "projection_kind": kind, "public_fields": fields}
    return {**projection, "projection_sha256": canonical_sha256(projection)}


def compare_common_fields(candidate: Any, historical_cases: Iterable[Any]) -> dict[str, Any]:
    """Reject identical observed causal records, retaining all incomparable cases as unknown."""
    fingerprint = common_field_fingerprint(candidate)
    matches, incomparable, compared = [], [], 0
    for case in historical_cases:
        raw = case.as_dict() if hasattr(case, "as_dict") else case
        if raw["suite_id"].split("-")[0] != "T322":
            continue
        try:
            other = common_field_fingerprint(raw)
        except (KeyError, TypeError, ValueError, StopIteration) as exc:
            incomparable.append({"case_sha256": canonical_sha256(raw), "reason": str(exc)})
            continue
        compared += 1
        if fingerprint["projection_sha256"] == other["projection_sha256"]:
            matches.append({"case_sha256": canonical_sha256(raw), "case_id": raw["case_id"]})
    return {"version": VERSION, "status": "REJECTED_COMMON_FIELD_DUPLICATE" if matches
            else "NO_OBVIOUS_COMMON_FIELD_DUPLICATE", "candidate": fingerprint,
            "compared_cases": compared, "matching_cases": matches, "incomparable_cases": incomparable,
            "global_novelty_proven": False, "required_pool_status": QUARANTINE,
            "limitation": "Public primary-record equality is a conservative rejection only; companion records, "
                          "runtime contracts and missing legacy facts are not proven equivalent."}
