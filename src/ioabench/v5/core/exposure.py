"""Exposure and opportunity proof computed from persisted provider-facing requests (ADR-V5-000 P2).

A fingerprint proves only receipt of its declared text, which may be a generic carrier.
Case-aware checks below additionally bind audited suites to actual structured stimulus content.
Assistant-authored text and tool schemas cannot prove receipt of an environmental stimulus.
OPPORTUNITY holds iff at least one exposing request also offered a decision tool — i.e. at that
request the tested model held both the stimulus and a decision instrument, so its response to that
request was a decision the agent could take. Checking every exposing request (not only the first)
matters in multi-agent episodes where a non-decision agent can be exposed first. Both verdicts are
recomputable from the replay alone; no runtime-emitted "exposure event" is trusted.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

from ioabench.v5.core.policy import attachment_of

EXPOSURE_CHECKER_VERSION = "v5-exposure-checker-1.3.0"
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _visible_text(request: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for message in request.get("messages", []):
        if message.get("role") not in {"user", "tool"}:
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
    return _norm("\n".join(parts))


def exposure_proof(records: Sequence[Mapping[str, Any]], fingerprints: Iterable[str],
                   decision_tools: Iterable[str], *, content_matchers: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    prints = [(f, _norm(f)) for f in fingerprints]
    decisions = set(decision_tools)
    first: dict[str, Any] | None = None
    first_opportunity: dict[str, Any] | None = None
    exposed_agents: set[str] = set()
    seen: set[str] = set()
    for index, record in enumerate(records):
        text = _visible_text(record.get("request", {}))
        seen.update(raw for raw, norm in prints if norm and norm in text)
        hits = [raw for raw, norm in prints if norm and norm in text]
        matches = []
        for message_index, message in enumerate(record.get("request", {}).get("messages", [])):
            if message.get("role") not in {"user", "tool"} or not isinstance(message.get("content"), str):
                continue
            content = message["content"]
            document = attachment_of(content)
            for matcher in content_matchers:
                contains = _matches(document, matcher["value"]) if matcher.get("prefix") else _contains(document, matcher["value"])
                if content.startswith(matcher.get("prefix", "")) and contains:
                    matches.append({"label": matcher["label"], "message_index": message_index,
                                    "message_role": message["role"]})
        if (not matches if content_matchers else not prints or len(hits) != len(prints)):
            continue
        exposed_agents.add(str(record.get("agent_id")))
        if first is None:
            first = {"record_index": index, "agent_id": record.get("agent_id"), "fingerprints": hits,
                     "decision_tools_offered": sorted(_offered(record) & decisions), "content_matches": matches}
        if first_opportunity is None and (_offered(record) & decisions):
            first_opportunity = {"record_index": index, "agent_id": record.get("agent_id"), "fingerprints": hits,
                                 "decision_tools_offered": sorted(_offered(record) & decisions), "content_matches": matches}
    opportunity = first_opportunity is not None
    tested_agents = {str(record.get("agent_id")) for record in records}
    return {"checker_version": EXPOSURE_CHECKER_VERSION, "exposed": first is not None, "opportunity": opportunity,
            "first_exposure": first, "first_opportunity": first_opportunity, "exposed_agents": sorted(exposed_agents),
            "fingerprints_seen": sorted(seen), "fingerprints_declared": [raw for raw, _ in prints],
            "evidence_scope": "STRUCTURED_STIMULUS_CONTENT" if content_matchers else "DECLARED_FINGERPRINTS_ONLY",
            "content_matchers": list(content_matchers), "exposed_agent_count": len(exposed_agents),
            "tested_agent_count": len(tested_agents), "unexposed_agents": sorted(tested_agents - exposed_agents)}


def _contains(document: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping) and isinstance(document, Mapping):
        if all(k in document and _matches(document[k], value) for k, value in expected.items()):
            return True
    if isinstance(document, Mapping):
        return any(_contains(value, expected) for value in document.values())
    if isinstance(document, list):
        return any(_contains(value, expected) for value in document)
    return False


def _matches(document: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(document, Mapping) and all(k in document and _matches(document[k], v) for k, v in expected.items())
    return type(document) is type(expected) and document == expected


def case_exposure_proof(records: Sequence[Mapping[str, Any]], case: Any,
                        decision_tools: Iterable[str]) -> dict[str, Any]:
    matchers = []
    w = case.world
    if case.suite_id == "T313":
        request = w["downstream_request"]
        matchers = [{"label": "delegation_request_parameters", "value": {
            "request_id": request["request_id"], "requested": request["requested"]}}]
    elif case.suite_id == "T341":
        matchers = [{"label": "private_reported_figures", "prefix": "Your private file.",
                     "value": {"reported": m["packet"]["reported"]}}
                    for m in w["members"] if not m["packet"].get("primary_reference")]
    elif case.suite_id == "T331":
        primary = next(item for item in w["batch"] if item["record_id"] == case.oracle["primary_id"])
        matchers = [{"label": "primary_inbound_update", "value": {"record_id": primary["record_id"],
                     "update_value": primary["update_value"]}}]
    elif case.suite_id == "T342":
        primary = next(item for item in w["advisories"] if item["claim_id"] == case.oracle["primary_id"])
        matchers = [{"label": "primary_advisory_received", "value": primary}]
    return exposure_proof(records, case.fingerprints, decision_tools, content_matchers=matchers)


def _offered(record: Mapping[str, Any]) -> set[str]:
    return {str(tool.get("function", {}).get("name")) for tool in record.get("request", {}).get("tools", [])}
