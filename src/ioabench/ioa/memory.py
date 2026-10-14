"""Per-agent, per-case working memory with explicit reset semantics."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class AgentMemory:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def put(self, key: str, value: Any) -> None:
        self._values[key] = deepcopy(value)

    def get(self, key: str, default: Any = None) -> Any:
        return deepcopy(self._values.get(key, default))

    def snapshot(self) -> Mapping[str, Any]:
        return deepcopy(self._values)

    def reset(self) -> None:
        self._values.clear()
