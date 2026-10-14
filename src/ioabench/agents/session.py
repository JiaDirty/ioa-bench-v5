"""Independent tested-agent model sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from ioabench.models import ModelPort, ModelProfile, ModelRequest, ModelResponse


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    organization_id: str
    role_id: str
    system_prompt: str
    capabilities: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()


@dataclass
class AgentSession:
    spec: AgentSpec
    model: ModelPort
    profile: ModelProfile
    messages: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)

    async def generate(self, content: str) -> ModelResponse:
        self.messages.append({"role": "user", "content": content})
        request = ModelRequest(
            messages=tuple([{"role": "system", "content": self.spec.system_prompt}, *self.messages]),
            parameters=self.profile.default_parameters,
            role_metadata={"agent_id": self.spec.agent_id, "organization_id": self.spec.organization_id, "role_id": self.spec.role_id},
        )
        response = await self.model.generate(self.profile, request)
        if response.text is not None:
            self.messages.append({"role": "assistant", "content": response.text})
        return response

    def receive_message(self, sender_id: str, content: str) -> None:
        self.messages.append({"role": "peer", "sender_id": sender_id, "content": content})

    def snapshot(self) -> dict[str, Any]:
        return {"agent_id": self.spec.agent_id, "messages": list(self.messages), "memory": dict(self.memory)}


class AgentSessionManager:
    def __init__(self, model: ModelPort, profile: ModelProfile) -> None:
        self.model = model
        self.profile = profile
        self._sessions: dict[str, AgentSession] = {}

    def create(self, spec: AgentSpec) -> AgentSession:
        if spec.agent_id in self._sessions:
            raise ValueError(f"agent session already exists: {spec.agent_id}")
        session = AgentSession(spec, self.model, self.profile)
        self._sessions[spec.agent_id] = session
        return session

    def get(self, agent_id: str) -> AgentSession:
        return self._sessions[agent_id]

    def send_message(self, sender_id: str, receiver_id: str, content: str) -> str:
        if sender_id == receiver_id:
            raise ValueError("an agent cannot send a peer message to itself")
        message_id = str(uuid4())
        self.get(receiver_id).receive_message(sender_id, content)
        return message_id
