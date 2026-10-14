"""Causal event ledger schema for the dynamic IoA world (dynamic-world phase M2, DW-020).

The v5 engine previously recorded bare ``{seq, turn, kind, payload}`` events. The dynamic world
requires an auditable causal ledger: every event names its actor, channel, visibility, authority
reference and the state hashes around the transition it caused, with stable ids and parent
links. Per 02_RUNTIME_AND_MEASUREMENT_DESIGN §4 the ledger covers only what the controlled
environment can observe — it never claims access to model-internal reasoning.

Compatibility contract: every event still carries the legacy keys (``seq``, ``turn``, ``kind``,
``payload``) so existing suite emitters and persisted replay consumers keep working; new fields
are additive. Evaluator-only payloads stay out of model-visible channels (the observation
firewall governs content, this module only stamps visibility labels).
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

EVENT_LEDGER_VERSION = "v5-event-ledger-1.0.0"

VISIBILITIES = ("model_visible", "environment", "evaluator")
CHANNELS = ("inbox", "tool_result", "world", "control")


def event_id(seq: int) -> str:
    return f"ev-{seq:04d}"


def make_event(seq: int, turn: int, kind: str, payload: Mapping[str, Any], *,
               actor: str | None = None, channel: str = "world",
               visibility: str = "environment", action: str | None = None,
               authority_reference: str | None = None, state_before_sha256: str | None = None,
               state_after_sha256: str | None = None, effects: Mapping[str, Any] | None = None,
               error: str | None = None, parent_seq: int | None = None) -> dict[str, Any]:
    if visibility not in VISIBILITIES:
        raise ValueError(f"unknown visibility {visibility!r}")
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    return {
        # legacy keys (unchanged semantics)
        "seq": seq, "turn": turn, "kind": kind, "payload": deepcopy(dict(payload)),
        # causal ledger keys (additive)
        "event_id": event_id(seq),
        "parent_event_id": None if parent_seq is None else event_id(parent_seq),
        "actor": actor, "channel": channel, "visibility": visibility, "action": action,
        "authority_reference": authority_reference,
        "state_before_sha256": state_before_sha256, "state_after_sha256": state_after_sha256,
        "effects": deepcopy(dict(effects)) if effects is not None else None,
        "error": error,
        "ledger_version": EVENT_LEDGER_VERSION,
    }


def inputs_digest(arguments: Mapping[str, Any]) -> str:
    """Stable digest of an action's inputs (no raw payloads duplicated into the ledger)."""
    return json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
