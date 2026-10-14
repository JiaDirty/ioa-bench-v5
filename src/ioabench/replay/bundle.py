"""Build deterministic evaluator-side case replay bundles.

The public agent view is deliberately derived without Oracle fields.  Oracle
references may be retained for evaluator joins, but never enter that view.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ioabench.hashing import canonical_sha256
from ioabench.telemetry import NormalizedEvent


_HIDDEN_KEYS = frozenset({
    "oracle", "oracle_db", "oracle_path", "ground_truth", "hidden_truth",
    "truth_label", "attack_label", "scoring_rules", "oracle_ref", "oracle_refs",
})


@dataclass(frozen=True)
class ReplayBundle:
    bundle_version: str
    run_id: str
    case_id: str
    scenario: Mapping[str, Any]
    world_snapshot: Mapping[str, Any]
    agents: tuple[Mapping[str, Any], ...]
    timeline: tuple[Mapping[str, Any], ...]
    model_records: tuple[Mapping[str, Any], ...]
    scorer_inputs: Mapping[str, Any]
    oracle_refs: tuple[str, ...]
    final_utility: Mapping[str, Any]
    content_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle_version": self.bundle_version,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "scenario": dict(self.scenario),
            "world_snapshot": dict(self.world_snapshot),
            "agents": [dict(agent) for agent in self.agents],
            "timeline": [dict(item) for item in self.timeline],
            "model_records": [dict(record) for record in self.model_records],
            "scorer_inputs": dict(self.scorer_inputs),
            "oracle_refs": list(self.oracle_refs),
            "final_utility": dict(self.final_utility),
            "content_sha256": self.content_sha256,
        }

    def tested_agent_view(self) -> dict[str, Any]:
        """Return only data that may be exposed to a tested agent."""

        return {
            "bundle_version": self.bundle_version,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "scenario": _public({key: value for key, value in self.scenario.items()
                                 if key in {"task", "registry_cards", "source_records", "sut_payload"}}),
        }

    def scorer_rebuild_inputs(self) -> dict[str, Any]:
        """Return stable references a scorer can use without hidden truth."""

        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "event_ids": [item["event_id"] for item in self.timeline if "event_id" in item],
            "message_ids": [item["message_id"] for item in self.timeline if item.get("message_id")],
            "delegation_ids": [item["delegation_id"] for item in self.timeline if item.get("delegation_id")],
            "action_ids": [item["action_id"] for item in self.timeline if item.get("action_id")],
            "model_record_ids": [record["record_id"] for record in self.model_records if record.get("record_id")],
            "tool_action_ids": [item["action_id"] for item in self.timeline if item.get("event_type", "").startswith("tool.") and item.get("action_id")],
            "utility": dict(self.final_utility),
        }

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return target


class ReplayBundleBuilder:
    def __init__(self, run_id: str, case_id: str, *, bundle_version: str = "replay-v1") -> None:
        self.run_id = run_id
        self.case_id = case_id
        self.bundle_version = bundle_version
        self._events: list[NormalizedEvent] = []
        self._model_records: list[Mapping[str, Any]] = []

    def add_event(self, event: NormalizedEvent) -> None:
        if event.run_id != self.run_id or event.case_id != self.case_id:
            raise ValueError("replay event belongs to another run or case")
        self._events.append(event)

    def add_events(self, events: Iterable[NormalizedEvent]) -> None:
        for event in events:
            self.add_event(event)

    def add_model_record(self, record: Mapping[str, Any]) -> None:
        value = dict(record)
        value.setdefault("record_id", canonical_sha256(value)[:16])
        self._model_records.append(value)

    def build(
        self,
        *,
        scenario: Mapping[str, Any],
        world_snapshot: Mapping[str, Any],
        agents: Iterable[Mapping[str, Any]],
        scorer_inputs: Mapping[str, Any] | None = None,
        oracle_refs: Iterable[str] = (),
        final_utility: Mapping[str, Any] | None = None,
    ) -> ReplayBundle:
        timeline = tuple(_event_dict(event) for event in sorted(self._events, key=lambda event: event.event_time))
        public_scorer_inputs = _public(scorer_inputs or {})
        payload = {
            "bundle_version": self.bundle_version,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "scenario": _public(scenario),
            "world_snapshot": _public(world_snapshot),
            "agents": [_public(agent) for agent in agents],
            "timeline": [_public(item) for item in timeline],
            "model_records": [_public(record) for record in self._model_records],
            "scorer_inputs": public_scorer_inputs,
            "oracle_refs": list(oracle_refs),
            "final_utility": _public(final_utility or {}),
        }
        return ReplayBundle(**payload, content_sha256=canonical_sha256(payload))


def _event_dict(event: NormalizedEvent) -> dict[str, Any]:
    value = {
        "event_id": event.event_id,
        "event_time": event.event_time,
        "observed_at": event.observed_at,
        "stage": event.stage,
        "event_type": event.event_type,
        "actor_agent_id": event.actor_agent_id,
        "target_agent_id": event.target_agent_id,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "parent_span_id": event.parent_span_id,
        "task_id": event.task_id,
        "message_id": event.message_id,
        "delegation_id": event.delegation_id,
        "claim_id": event.claim_id,
        "action_id": event.action_id,
        "protocol": event.protocol,
        "protocol_version": event.protocol_version,
        "outcome": event.outcome,
        "error_class": event.error_class,
        "payload_sha256": event.payload_sha256,
        "attributes": dict(event.attributes),
    }
    return {key: item for key, item in value.items() if item is not None}


def _public(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _public(item) for key, item in value.items() if str(key).casefold() not in _HIDDEN_KEYS}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_public(item) for item in value]
    return value
