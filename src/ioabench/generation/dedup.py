"""Deterministic exact and lightweight structural near-deduplication."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256


class Deduplicator:
    def __init__(self, *, near_threshold: float = 0.9) -> None:
        if not 0 < near_threshold <= 1:
            raise ValueError("near_threshold must be in (0, 1]")
        self.near_threshold = near_threshold
        self._exact: set[str] = set()
        self._tokens: list[set[str]] = []

    def signature(self, value: Mapping[str, Any]) -> str:
        return canonical_sha256(_normalize(value))

    def add(self, value: Mapping[str, Any]) -> bool:
        signature = self.signature(value)
        tokens = _tokenize(value)
        duplicate = signature in self._exact or any(_jaccard(tokens, previous) >= self.near_threshold for previous in self._tokens)
        if duplicate:
            return False
        self._exact.add(signature)
        self._tokens.append(tokens)
        return True


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    return value


def _tokenize(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", str(_normalize(value)).casefold()))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0
