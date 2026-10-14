"""Append-only cross-run family registry (post-audit DEDUP-01).

One JSONL registry per experimental namespace records every accepted family: its suite, slice,
family id, executable-structure digest, originating run and novelty evidence. New batches must
classify each candidate family against this registry BEFORE claiming novelty:

* ``instance_of_existing`` — digest matches a registered family of the same suite: the pair set
  is a legitimate new INSTANCE of a known family (kept, but it does not increase the effective
  family count);
* ``new_family`` — no registered digest matches and the registry is non-empty: novelty evidence
  (nearest neighbour + structural dimensions) is recorded at registration time;
* ``NO_REFERENCE`` — the registry has no entries for the suite: novelty is NOT proven, the run
  is the reference-establishing batch.

The registry is append-only: entries are never rewritten or removed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REGISTRY_VERSION = "v5-family-registry-1.0.0"


def register(registry_path: Path, *, suite_id: str, family_id: str, digest: str, run_id: str,
             evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    entry = {
        "registry_version": REGISTRY_VERSION,
        "suite_id": suite_id,
        "family_id": family_id,
        "digest": digest,
        "run_id": run_id,
        "registered_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence": dict(evidence or {}),
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def load(registry_path: Path, *, suite_id: str | None = None) -> list[dict[str, Any]]:
    if not registry_path.exists():
        return []
    entries = []
    with registry_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if suite_id is None or entry.get("suite_id") == suite_id:
                entries.append(entry)
    return entries


def classify(registry_path: Path, *, suite_id: str, digest: str) -> dict[str, Any]:
    """Classify a candidate family digest against the registry for its suite."""
    entries = [e for e in load(registry_path, suite_id=suite_id) if e.get("digest") == digest]
    suite_entries = load(registry_path, suite_id=suite_id)
    if not suite_entries:
        return {"status": "NO_REFERENCE", "matching_families": [],
                "note": "registry has no entries for this suite; novelty is NOT proven by an "
                        "empty reference"}
    if entries:
        return {"status": "instance_of_existing",
                "matching_families": sorted({e["family_id"] for e in entries}),
                "note": "legitimate new instance of a registered family; does not increase the "
                        "effective family count"}
    return {"status": "new_family", "matching_families": [],
            "nearest_neighbors": _nearest(suite_entries, digest)}


def _nearest(suite_entries: list[dict[str, Any]], digest: str) -> list[str]:
    """Registered digests adjacent to the candidate (hex-distance over the digest string)."""
    scored = []
    for entry in suite_entries:
        other = entry.get("digest", "")
        if len(other) == len(digest):
            distance = sum(1 for a, b in zip(digest, other) if a != b)
            scored.append((distance, entry["family_id"], other))
    scored.sort()
    return [f"{fid}({dist})" for dist, fid, _ in scored[:3]]
