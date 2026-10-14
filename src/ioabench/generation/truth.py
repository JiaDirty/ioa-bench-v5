"""Evaluator-owned, immutable programmatic truth."""

from __future__ import annotations

from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any, Mapping

from ioabench.hashing import canonical_json_bytes, canonical_sha256


@dataclass(frozen=True, init=False)
class GroundTruth:
    _content: bytes

    def __init__(self, facts: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_content", canonical_json_bytes(facts))

    @property
    def facts(self) -> Mapping[str, Any]:
        return MappingProxyType(self.as_dict())

    @property
    def content_sha256(self) -> str:
        return canonical_sha256(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self._content)
