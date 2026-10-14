"""Keep tested-agent runtime inputs inside the local synthetic environment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from ioabench.storage.sqlite import LocalStores, StoreRole


class PublicWebUnavailable(PermissionError):
    """Raised when formal tools attempt to access a public-web capability."""


@dataclass(frozen=True)
class AgentEnvironment:
    agent_id: str
    visible_paths: Mapping[str, Path]
    allowed_tools: frozenset[str]

    def has_oracle_access(self) -> bool:
        return "oracle" in self.visible_paths or any("oracle" in str(path).lower() for path in self.visible_paths.values())


class FormalToolPolicy:
    def __init__(self, allowed_tools: frozenset[str] | None = None) -> None:
        self.allowed_tools = allowed_tools or frozenset({"a2a", "mcp", "sandbox", "knowledge"})

    def check(self, tool: str, target: str | None = None) -> None:
        if tool not in self.allowed_tools:
            raise PermissionError(f"tool is unavailable in formal local-v1: {tool}")
        if target and urlparse(target).scheme in {"http", "https", "ftp"}:
            raise PublicWebUnavailable("public-web access is disabled in formal local-v1")


def build_agent_environment(stores: LocalStores, agent_id: str = "agent") -> AgentEnvironment:
    return AgentEnvironment(
        agent_id=agent_id,
        visible_paths={"sut": stores.paths[StoreRole.SUT]},
        allowed_tools=FormalToolPolicy().allowed_tools,
    )
