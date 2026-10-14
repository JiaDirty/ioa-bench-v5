import asyncio

import pytest

from ioabench.sandbox import ActionBudget, SandboxCore


def test_sandbox_mutations_are_transactional_and_replayable() -> None:
    sandbox = SandboxCore(ActionBudget(3, 3, 3, 3))
    asyncio.run(sandbox.reset_world({"invoice": {"status": "open"}}))
    updated = asyncio.run(sandbox.execute("agent-1", "set", {"key": "invoice", "value": {"status": "paid"}}, "a-1"))
    duplicate = asyncio.run(sandbox.execute("agent-1", "set", {"key": "invoice", "value": {"status": "bad"}}, "a-1"))
    with pytest.raises(ValueError):
        asyncio.run(sandbox.execute("agent-1", "unknown", {"key": "invoice"}, "a-2"))

    assert updated == duplicate
    assert asyncio.run(sandbox.snapshot())["invoice"]["status"] == "paid"
    assert sandbox.action_log()[0]["action_id"] == updated["action_id"]
    assert sandbox.action_log()[-1]["status"] == "ERROR"
    assert sandbox.action_log()[-1]["before"] == sandbox.action_log()[-1]["after"]
