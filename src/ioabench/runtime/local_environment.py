"""No-Docker local lifecycle for the reference IoA components."""

from __future__ import annotations

import inspect
from enum import StrEnum
from typing import Any, Mapping


class EnvironmentState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    KILLED = "killed"


class LocalEnvironment:
    def __init__(self, *, telemetry: Any | None = None) -> None:
        self.telemetry = telemetry
        self.state = EnvironmentState.STOPPED
        self.active_case_id: str | None = None
        self._components: list[tuple[str, Any]] = []
        self._mutations_enabled = False

    def register(self, name: str, component: Any) -> None:
        if self.state is not EnvironmentState.STOPPED:
            raise RuntimeError("components can only be registered while stopped")
        if any(existing_name == name for existing_name, _ in self._components):
            raise ValueError(f"component already registered: {name}")
        self._components.append((name, component))

    async def start(self) -> None:
        if self.state is EnvironmentState.RUNNING:
            return
        if self.state is EnvironmentState.KILLED:
            raise RuntimeError("killed environment must be recreated")
        for _, component in self._components:
            await _call(component, "start")
        self.state = EnvironmentState.RUNNING
        self._mutations_enabled = True

    async def reset_case(self, case_id: str, world_snapshot: Mapping[str, Any]) -> None:
        self._require_running()
        self.active_case_id = case_id
        for _, component in self._components:
            if hasattr(component, "reset_world"):
                await _call(component, "reset_world", world_snapshot)
            elif hasattr(component, "reset"):
                await _call(component, "reset")

    async def stop(self) -> None:
        if self.state is not EnvironmentState.RUNNING:
            return
        self._mutations_enabled = False
        for _, component in reversed(self._components):
            await _call(component, "stop")
        await self._flush()
        self.active_case_id = None
        self.state = EnvironmentState.STOPPED

    async def kill(self, *, run_id: str | None = None, reason: str = "kill_switch") -> Mapping[str, Any]:
        if self.state is EnvironmentState.KILLED:
            return {"status": "KILLED", "reason": reason, "run_id": run_id}
        self._mutations_enabled = False
        for _, component in reversed(self._components):
            await _call(component, "cancel")
            await _call(component, "stop")
        await self._flush(run_id)
        self.active_case_id = None
        self.state = EnvironmentState.KILLED
        return {"status": "KILLED", "reason": reason, "run_id": run_id}

    def assert_mutations_allowed(self) -> None:
        if not self._mutations_enabled or self.state is not EnvironmentState.RUNNING:
            raise RuntimeError("environment is not accepting sandbox mutations")

    def _require_running(self) -> None:
        if self.state is not EnvironmentState.RUNNING:
            raise RuntimeError("environment is not running")

    async def _flush(self, run_id: str | None = None) -> None:
        if self.telemetry is not None and hasattr(self.telemetry, "flush"):
            await _call(self.telemetry, "flush", run_id or "")


LocalEnvironmentManager = LocalEnvironment


async def _call(component: Any, method_name: str, *args: Any) -> Any:
    method = getattr(component, method_name, None)
    if method is None:
        return None
    result = method(*args)
    return await result if inspect.isawaitable(result) else result
