"""Structural signatures for dynamic-world cases (M4, DW-041).

A signature captures the EXECUTED STRUCTURE of a case — world shape, tool graph, mechanism
slots, evidence carriers, agent roles, delivery/event schedule — with entity names, ids and
numbers normalized away. Two cases with the same signature differ only on the surface (行业/
实体名/数字) and belong to the same family; a genuinely new task/evidence/interaction structure
must differ on at least one structural dimension.

This is the dedup primitive the data factory (M5) will use against the candidate pool and the
frozen 5.1.5/5.1.6 datasets: novelty claims are verified against compiled signatures, never
taken from the generator's say-so (03_DATA_FACTORY §2).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SIGNATURE_VERSION = "v5-structural-signature-0.2.0"
STRUCTURE_VERSION = "v5-executable-structure-1.0.0"

_ENTITY = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][a-z]+[ -]){1,3}[A-Z][a-z]+(?![a-z])")
_DIGITS = re.compile(r"\d+")
_TOKEN_WORDS = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _normalize_value(value: Any) -> Any:
    """Strip surface variation: long name-like phrases and numbers collapse to placeholders."""
    if isinstance(value, Mapping):
        return {str(k): _normalize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    if isinstance(value, str):
        text = _ENTITY.sub("<NAME>", value)
        text = _DIGITS.sub("<N>", text)
        return text
    return value


def _shape(value: Any, depth: int = 0) -> Any:
    """Type/keys shape of a document (structure without content)."""
    if depth > 8:
        return "..."
    if isinstance(value, Mapping):
        return {str(k): _shape(v, depth + 1) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        if not value:
            return []
        return {"list_of": [_shape(v, depth + 1) for v in value[:3]]}
    return type(value).__name__


def signature(case: Mapping[str, Any]) -> dict[str, Any]:
    """Full signature (metadata + structure) — used for replay-integrity hashing where the
    complete case identity matters."""
    world = case.get("world", {})
    return {
        "signature_version": SIGNATURE_VERSION,
        "suite_id": case.get("suite_id"),
        "subtype": case.get("subtype"),
        "difficulty": case.get("difficulty"),
        "arm": case.get("arm"),
        "mechanism_slots": sorted(case.get("mechanism_slots", [])),
        "fingerprints_normalized": [_normalize_value(f) for f in case.get("fingerprints", [])],
        "world_shape": _shape(world),
        "world_normalized_keys": sorted(str(k) for k in world),
        "carrier_text_normalized": _normalize_value(json.dumps(
            {k: world[k] for k in sorted(world) if isinstance(world.get(k), str)}, sort_keys=True)),
    }


def executable_structure_signature(case: Mapping[str, Any]) -> dict[str, Any]:
    """The normalized EXECUTABLE-STRUCTURE projection (post-audit FAMILY-01): the task/evidence/
    authorization/tool-path semantics only — suite_id, subtype, difficulty, arm and domain are
    sample metadata and are deliberately EXCLUDED. This projection is the single source shared
    by ``structural_delta`` (same-family determination) and ``family_digest`` (hash/index).

    Accepts either a raw Case mapping (has a ``world`` key) or an existing full ``signature()``
    output (has ``world_shape`` at the top level; metadata fields are stripped).
    """
    if "world" in case:
        world = case.get("world", {})
        return {
            "structure_version": STRUCTURE_VERSION,
            "mechanism_slots": sorted(case.get("mechanism_slots", [])),
            "fingerprints_normalized": [_normalize_value(f) for f in case.get("fingerprints", [])],
            "world_shape": _shape(world),
            "world_normalized_keys": sorted(str(k) for k in world),
            "carrier_text_normalized": _normalize_value(json.dumps(
                {k: world[k] for k in sorted(world) if isinstance(world.get(k), str)},
                sort_keys=True)),
        }
    if "world_shape" in case:
        # already a full signature: strip metadata, keep the pre-computed structure fields
        return {
            "structure_version": STRUCTURE_VERSION,
            "mechanism_slots": sorted(case.get("mechanism_slots", [])),
            "fingerprints_normalized": case.get("fingerprints_normalized", []),
            "world_shape": case.get("world_shape"),
            "world_normalized_keys": case.get("world_normalized_keys", []),
            "carrier_text_normalized": case.get("carrier_text_normalized"),
        }
    raise ValueError("input is neither a Case mapping nor a full signature")


def family_digest(case: Mapping[str, Any]) -> str:
    """Family-identity hash over the executable structure projection (metadata excluded)."""
    return signature_digest(executable_structure_signature(case))


def metadata_differences(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """Sample-metadata differences (suite/subtype/difficulty) — informational labels, never
    family-proof on their own (post-audit FAMILY-01)."""
    fields = ("suite_id", "subtype", "difficulty", "arm", "domain")
    return {field: [a.get(field), b.get(field)]
            for field in fields if a.get(field) != b.get(field)}


def signature_digest(sig: Mapping[str, Any]) -> str:
    payload = json.dumps(sig, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def structural_delta(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """Which structural dimensions differ between two signatures.

    Post-audit FAMILY-01: the comparison operates on the EXECUTABLE-STRUCTURE projection
    (metadata excluded). Suite/subtype/difficulty differences are reported separately as
    ``metadata_differences`` — labels alone never prove or break a family. If the executable
    structures match but the suite_ids differ, the result is flagged
    ``cross_suite_same_structure``/``requires_human`` instead of auto-merging families across
    scientific constructs.
    """
    exec_a = executable_structure_signature(a)
    exec_b = executable_structure_signature(b)
    dimensions: list[str] = []
    for field in ("mechanism_slots",):
        if exec_a.get(field) != exec_b.get(field):
            dimensions.append(field)
    if exec_a.get("world_shape") != exec_b.get("world_shape"):
        dimensions.append("world_shape")
    if exec_a.get("world_normalized_keys") != exec_b.get("world_normalized_keys"):
        dimensions.append("world_keys")
    if exec_a.get("fingerprints_normalized") != exec_b.get("fingerprints_normalized"):
        dimensions.append("evidence_carriers")
    if exec_a.get("carrier_text_normalized") != exec_b.get("carrier_text_normalized"):
        dimensions.append("carrier_structure")
    same_structure = not dimensions
    cross_suite = a.get("suite_id") != b.get("suite_id")
    result: dict[str, Any] = {
        "dimensions": dimensions,
        "same_family": same_structure and not cross_suite,
        "cross_suite_same_structure": bool(same_structure and cross_suite),
        "requires_human": bool(same_structure and cross_suite),
        "metadata_differences": metadata_differences(a, b),
        "signature_version": SIGNATURE_VERSION,
        "structure_version": STRUCTURE_VERSION,
    }
    return result
