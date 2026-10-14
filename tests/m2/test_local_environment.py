import asyncio

import pytest

from ioabench.runtime.local_environment import EnvironmentState, LocalEnvironment
from ioabench.sandbox import ActionBudget, SandboxCore


class _Telemetry:
    def __init__(self) -> None:
        self.flushed: list[str] = []

    async def flush(self, run_id: str) -> None:
        self.flushed.append(run_id)


def test_local_environment_resets_world_and_kill_flushes() -> None:
    telemetry = _Telemetry()
    sandbox = SandboxCore(ActionBudget(3, 3, 3, 3))
    environment = LocalEnvironment(telemetry=telemetry)
    environment.register("sandbox", sandbox)

    asyncio.run(environment.start())
    asyncio.run(environment.reset_case("case-1", {"value": "initial"}))
    asyncio.run(sandbox.execute("agent-1", "set", {"key": "value", "value": "changed"}, "a-1"))
    asyncio.run(environment.reset_case("case-2", {"value": "fresh"}))
    assert asyncio.run(sandbox.snapshot())["value"] == "fresh"

    result = asyncio.run(environment.kill(run_id="run-1", reason="test"))
    assert result["status"] == "KILLED"
    assert environment.state is EnvironmentState.KILLED
    assert telemetry.flushed == ["run-1"]


def test_stopped_environment_rejects_mutation_gate() -> None:
    environment = LocalEnvironment()
    with pytest.raises(RuntimeError):
        environment.assert_mutations_allowed()
