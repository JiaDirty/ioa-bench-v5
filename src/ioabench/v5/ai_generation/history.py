"""Hash-bound historical case index, including rejected executable proposals.

The index reuses quality.py's runtime projection. It does not promote static differences to
verified families, and it never exports Oracle fields into the public dedup evidence.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.core.case import CASE_SCHEMA_VERSION, SUITES, case_from_dict
from .quality import QUALITY_VERSION, _shape, classify_candidate, dedup_features

HISTORY_VERSION = "ioabench.v5.generation-history/1.2.0"
PROBE_VERSION = "ioabench.v5.behavioral-probe/1.1.0"
POLICY_CONTRACT = "ioabench.v5.historical-witness-naive/1.0.0"
_PREFIXES = ("case", "pair", "rejected")


def discover_sources(root: Path) -> list[Path]:
    """Inventory experimental case containers, excluding copied tests/source snapshots."""
    sources = []
    for folder in (root / "data/v5", root / "artifacts/v5"):
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            relative = path.relative_to(folder)
            if (not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}
                    or any(part.startswith(("pytest", "test_")) or part in {"source", "__pycache__"}
                           for part in relative.parts)):
                continue
            if not path.stem.lower().startswith(_PREFIXES) and CASE_SCHEMA_VERSION.encode() not in path.read_bytes():
                continue
            sources.append(path)
    return sorted(set(sources))


def _cases(value: Any, pointer: str = "") -> Iterable[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        if value.get("schema_version") == CASE_SCHEMA_VERSION:
            yield pointer, value
            return
        for key, child in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            yield from _cases(child, pointer + "/" + token)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _cases(child, pointer + "/" + str(index))


def _scenario(suite_id: str) -> Any:
    from ioabench.v5.dynamic.registry import DYNAMIC_MODULES, get_adapter
    from ioabench.v5.dynamic.runner import _resolve_scenario
    from ioabench.v5.suites import load

    if suite_id in DYNAMIC_MODULES:
        return _resolve_scenario(get_adapter(suite_id))
    if suite_id in SUITES:
        return getattr(load(suite_id), f"{suite_id}Scenario")()
    raise ValueError(f"unregistered historical suite: {suite_id}")


def build_index(root: Path, *, sources: Iterable[Path] | None = None) -> dict[str, Any]:
    """Read immutable source bytes once and retain every source/status occurrence.

    Sources omitted from the supported on-disk discovery scope remain explicit limitations;
    ZIP archives and malformed/uncompiled proposals cannot prove historical novelty.
    """
    root = root.resolve()
    projection_source = source_tree_hash(root)
    paths = sorted(set(discover_sources(root) if sources is None else sources))
    bindings: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    findings = []
    empty_sources = []
    for path in paths:
        path = path.resolve()
        name = path.relative_to(root).as_posix()
        content = path.read_bytes()
        bindings[name] = sha256(content).hexdigest()
        result_path = path.parent / "RESULT.json"
        result = {}
        found = 0
        try:
            if result_path.is_file():
                result_bytes = result_path.read_bytes()
                bindings[result_path.relative_to(root).as_posix()] = sha256(result_bytes).hexdigest()
                result = json.loads(result_bytes)
            status = result.get("status", "REJECTED" if "reject" in path.stem.lower() else "HISTORICAL_UNQUALIFIED")
            text = content.decode("utf-8-sig")
            documents = ((number, json.loads(line)) for number, line in enumerate(text.splitlines(), 1) if line.strip()) if path.suffix.lower() == ".jsonl" else [(None, json.loads(text))]
            for line, document in documents:
                for pointer, raw in _cases(document):
                    found += 1
                    case = case_from_dict(raw, allow_dynamic=True)
                    digest = case.content_sha256()
                    if digest not in records:
                        try:
                            features = dedup_features(case, scenario=_scenario(case.suite_id))
                        except (KeyError, TypeError, ValueError, IndexError) as exc:
                            features = dedup_features(case)
                            findings.append({"source": name, "line": line, "pointer": pointer,
                                             "suite_id": case.suite_id, "code": "RUNTIME_PROJECTION_UNAVAILABLE",
                                             "reason": str(exc)})
                        records[digest] = {"case_sha256": digest, "features": features, "occurrences": [],
                                           "behavioral_probe_signature": None}
                    records[digest]["occurrences"].append({"source": name, "line": line,
                        "pointer": pointer, "status": status,
                        "scientific_qualification": "NOT_ESTABLISHED_BY_INDEX"})
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            findings.append({"source": name, "code": "SOURCE_NOT_INDEXABLE", "reason": str(exc)})
        if not found:
            empty_sources.append(name)
    if source_tree_hash(root) != projection_source:
        raise ValueError("runtime projection source changed during indexing; retry as a new run")
    return {"index_version": HISTORY_VERSION, "feature_version": QUALITY_VERSION,
            "projection_source_sha256": projection_source,
            "discovery_mode": "AUTO" if sources is None else "EXPLICIT",
            "discovered_sources": [path.resolve().relative_to(root).as_posix() for path in paths],
            "source_sha256": bindings, "records": list(records.values()), "findings": findings,
            "sources_without_cases": empty_sources,
            "scope": {"roots": ["data/v5", "artifacts/v5"],
                      "container_prefixes": list(_PREFIXES), "additional_containers": "ALL_JSON_WITH_CASE_SCHEMA_MARKER", "archives": "NOT_SCANNED",
                      "test_fixtures_and_source_copies": "EXCLUDED",
                      "uncompiled_proposals": "NOT_EXECUTABLE_REFERENCES"},
            "summary": {"sources": len(bindings), "unique_cases": len(records),
                        "occurrences": sum(len(row["occurrences"]) for row in records.values()),
                        "occurrence_statuses": dict(Counter(item["status"] for row in records.values()
                                                             for item in row["occurrences"])),
                        "verified_new_families": 0}}


def behavioral_signature(case: Any, results: Mapping[str, Mapping[str, Any]], *,
                         policy_contract: str) -> dict[str, Any]:
    """Project real completed deterministic runner traces, retaining source hashes separately."""
    if not policy_contract or not {"witness", "naive"} <= set(results):
        raise ValueError("fixed witness and naive policy traces and a versioned contract are required")
    raw = case.as_dict() if hasattr(case, "as_dict") else case
    digest = canonical_sha256(raw)
    scenario = _scenario(raw["suite_id"])
    identities = {agent.agent_id: f"agent:{index}" for index, agent in enumerate(scenario.agents(raw["world"]))}
    behavior = {}
    for policy, result in sorted(results.items()):
        trace = result.get("trace", {})
        integrity = result.get("monitor_report", {}).get("ledger_integrity", {})
        if (result.get("case_sha256") != digest or result.get("status") != "COMPLETED"
                or result.get("model_id") != "reference-policy" or integrity.get("passed") is not True
                or not trace.get("actions") or canonical_sha256(trace.get("records")) != trace.get("records_sha256")):
            raise ValueError("behavioral proof requires case-bound complete reference-policy runner evidence")
        behavior[policy] = {
            "actions": [{"actor": identities.get(action["actor"], action["actor"]),
                         "tool": action["tool"], "status": action["status"],
                         "arguments": _shape(action["arguments"], identities),
                         "result": _shape(action["result"], identities),
                         "state_changed": action["state_before_sha256"] != action["state_after_sha256"]}
                        for action in trace["actions"]],
            "events": [{"kind": event["kind"], "turn": event.get("turn"), "actor": identities.get(event.get("actor"), event.get("actor")),
                        "channel": event.get("channel"), "visibility": event.get("visibility"),
                        "action": event.get("action"), "parent": event.get("parent_event_id"),
                        "payload_shape": _shape(event.get("payload"), identities),
                        "state_changed": event.get("state_before_sha256") != event.get("state_after_sha256")}
                       for event in trace["events"]],
            "final_state_shape": _shape(trace["final_state"], identities)}
    return {"probe_version": PROBE_VERSION, "policy_contract": policy_contract,
            "case_sha256": digest, "behavior": behavior,
            "evidence_sha256": {policy: canonical_sha256(result) for policy, result in sorted(results.items())}}


def attach_probe(index: dict[str, Any], case: Any, results: Mapping[str, Mapping[str, Any]], *,
                 policy_contract: str) -> dict[str, Any]:
    probe = behavioral_signature(case, results, policy_contract=policy_contract)
    row = next((row for row in index["records"] if row["case_sha256"] == probe["case_sha256"]), None)
    if row is None:
        raise ValueError("behavioral trace case is absent from the historical index")
    existing = row.get("behavioral_probe_signature")
    if existing is not None and existing != probe:
        raise ValueError("historical behavioral evidence changed; use a new versioned index")
    row["behavioral_probe_signature"] = probe
    return probe


def verify_sources(root: Path, index: Mapping[str, Any]) -> None:
    """Fail closed if a pinned historical source is missing or changed."""
    if index.get("index_version") != HISTORY_VERSION or index.get("feature_version") != QUALITY_VERSION:
        raise ValueError("historical index version changed; rebuild from raw case sources")
    root = root.resolve()
    if source_tree_hash(root) != index.get("projection_source_sha256"):
        raise ValueError("runtime projection source changed; build a new versioned index")
    if index.get("discovery_mode") == "AUTO" and index.get("discovered_sources") != [
            path.resolve().relative_to(root).as_posix() for path in discover_sources(root)]:
        raise ValueError("historical source inventory changed; build a new versioned index")
    for name, expected in index["source_sha256"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"historical source changed or missing: {name}")


def classify(candidate: Any, index: Mapping[str, Any], *, scenario: Any,
             behavioral_probe_signature: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Use the authoritative quality features, retaining uncertain novelty as a candidate."""
    if index.get("index_version") != HISTORY_VERSION or index.get("feature_version") != QUALITY_VERSION:
        raise ValueError("historical index version changed; rebuild from raw case sources")
    raw = candidate.as_dict() if hasattr(candidate, "as_dict") else candidate
    suite = raw["suite_id"].split("-")[0]
    records = [row for row in index["records"] if row["features"]["suite_id"].split("-")[0] == suite]
    result = classify_candidate(candidate, [row["features"] for row in records], scenario=scenario)
    result.update(index_version=HISTORY_VERSION, legacy_status=result["status"], new_family=False,
                  historical_sources=len(index["source_sha256"]), behavioral_status="NOT_RUN")
    if any(finding.get("suite_id", suite).split("-")[0] == suite for finding in index["findings"]):
        return {**result, "status": "INDETERMINATE", "reason": "Relevant historical sources could not be projected completely."}
    status = {"EXACT_DUPLICATE": "EXACT_DUPLICATE", "TEXT_DUPLICATE": "NEAR_DUPLICATE",
              "INSTANCE": "VALID_FAMILY_INSTANCE", "NO_REFERENCE": "INDETERMINATE",
              "NEW_STRUCTURE": "CANDIDATE_NEW_FAMILY"}[result["legacy_status"]]
    result["status"] = status
    if status in {"VALID_FAMILY_INSTANCE", "CANDIDATE_NEW_FAMILY"} and any(
            not row["features"].get("runtime_verified") for row in records):
        result.update(status="INDETERMINATE", reason="A historical runtime structure is unverified.")
        status = result["status"]
    if status == "CANDIDATE_NEW_FAMILY" and behavioral_probe_signature is not None:
        probes = [row.get("behavioral_probe_signature") for row in records]
        if probes and all(probes):
            comparable = (behavioral_probe_signature.get("case_sha256") == canonical_sha256(raw)
                          and behavioral_probe_signature.get("probe_version") == PROBE_VERSION
                          and all(probe.get("case_sha256") == row["case_sha256"]
                             and probe.get("probe_version") == behavioral_probe_signature.get("probe_version")
                             and probe.get("policy_contract") == behavioral_probe_signature.get("policy_contract")
                             and probe.get("evidence_sha256") and probe.get("behavior")
                             for probe, row in zip(probes, records)))
            if comparable and all(probe["behavior"] != behavioral_probe_signature.get("behavior") for probe in probes):
                result.update(status="VERIFIED_NEW_FAMILY", new_family=True, behavioral_status="DISTINCT_UNDER_FIXED_PROBES")
            else:
                result.update(status="INDETERMINATE", behavioral_status="NOT_DISTINGUISHED_OR_INCOMPARABLE")
    result["evidence_sha256"] = canonical_sha256(result)
    return result
