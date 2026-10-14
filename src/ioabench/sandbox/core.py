"""Transactional synthetic-world sandbox with replayable action records."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .budget import ActionBudget


@dataclass(frozen=True)
class ActionRecord:
    action_id: str
    actor_id: str
    operation: str
    arguments: Mapping[str, Any]
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    status: str
    error: str | None = None
    occurred_at: str = ""


class SandboxCore:
    def __init__(self, budget: ActionBudget) -> None:
        self.budget = budget
        self._state: dict[str, Any] = {}
        self._actions: list[ActionRecord] = []
        self._idempotency: dict[str, Mapping[str, Any]] = {}

    async def reset_world(self, world_snapshot: Mapping[str, Any]) -> None:
        self._state = deepcopy(dict(world_snapshot))
        self._actions.clear()
        self._idempotency.clear()

    async def execute(self, actor_id: str, operation: str, arguments: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]:
        if idempotency_key in self._idempotency:
            return dict(self._idempotency[idempotency_key])
        self.budget.consume_tool_call()
        before = deepcopy(self._state)
        action_id = f"action-{len(self._actions) + 1}"
        try:
            result = self._apply(operation, arguments)
        except Exception as exc:
            self._state = before
            record = ActionRecord(action_id, actor_id, operation, dict(arguments), before, before, "ERROR", str(exc), _now())
            self._actions.append(record)
            raise
        after = deepcopy(self._state)
        response = {"action_id": action_id, "status": "OK", "result": result}
        self._actions.append(ActionRecord(action_id, actor_id, operation, dict(arguments), before, after, "OK", occurred_at=_now()))
        self._idempotency[idempotency_key] = response
        return response

    async def snapshot(self) -> Mapping[str, Any]:
        return deepcopy(self._state)

    def action_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(action) for action in self._actions)

    def _apply(self, operation: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        key = str(arguments.get("key", ""))
        if not key:
            raise ValueError("sandbox operation requires key")
        if operation == "read":
            return {"key": key, "value": deepcopy(self._state.get(key))}
        if operation == "set":
            self._state[key] = deepcopy(arguments.get("value"))
            return {"key": key, "value": deepcopy(self._state[key])}
        if operation == "delete":
            return {"key": key, "deleted": self._state.pop(key, None) is not None}
        raise ValueError(f"unsupported sandbox operation: {operation}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
