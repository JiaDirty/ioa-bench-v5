"""Phrasebank: authored text templates plus validated generator-model paraphrases (ADR-V5-000 P11).

Suite generators draw every natural-language template through ``variants(suite, key, authored)``. The bank file
``data/v5/phrasebank/<suite>.json`` (built by scripts/v5/naturalize_phrasebank.py with an independent generator
model) only ever *adds* variants; each added variant preserved the exact placeholder set, passed the observation
firewall and a length bound when it was admitted. Truth never depends on generated prose: placeholders carry every
programmatic value. Both arms of a pair are rendered from the same chosen shared variants, so pairing is unaffected.
"""
from __future__ import annotations

import json
import string
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from ioabench.v5.core.firewall import ObservationFirewall

PHRASEBANK_VERSION = "v5-phrasebank-1.0.0"
BANK_DIR = Path(__file__).resolve().parents[3] / "data" / "v5" / "phrasebank"
_FORMATTER = string.Formatter()


def placeholders(template: str) -> frozenset[str]:
    return frozenset(name for _, name, _, _ in _FORMATTER.parse(template) if name)


@lru_cache(maxsize=None)
def _bank(suite: str) -> dict[str, list[str]]:
    path = BANK_DIR / f"{suite}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: [v["text"] for v in entries if v.get("admitted")] for key, entries in data.get("entries", {}).items()}


def variants(suite: str, key: str, authored: Sequence[str]) -> list[str]:
    """Authored variants first, then admitted bank variants for ``key`` (deterministic order)."""
    return list(authored) + [v for v in _bank(suite).get(key, []) if v not in authored]


def admissible(candidate: str, source: str) -> tuple[bool, str]:
    if placeholders(candidate) != placeholders(source):
        return False, "placeholder set changed"
    if not 0.6 * len(source) <= len(candidate) <= 1.5 * len(source):
        return False, "length out of bounds"
    if ObservationFirewall().scan(candidate):
        return False, "evaluator vocabulary"
    try:
        candidate.format(**{name: "x" for name in placeholders(candidate)})
    except (KeyError, IndexError, ValueError):
        return False, "template does not format"
    return True, "ok"
