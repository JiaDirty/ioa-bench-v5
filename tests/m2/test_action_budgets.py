import asyncio

import pytest

from ioabench.sandbox import ActionBudget, BudgetExceeded, SandboxCore


def test_all_budget_dimensions_are_enforced() -> None:
    budget = ActionBudget(1, 1, 1, 1)
    budget.consume_round()
    budget.consume_model_call()
    budget.consume_peer_message()
    budget.consume_tool_call()
    for consume in (budget.consume_round, budget.consume_model_call, budget.consume_peer_message, budget.consume_tool_call):
        with pytest.raises(BudgetExceeded):
            consume()


def test_sandbox_tool_budget_blocks_unbounded_mutations() -> None:
    sandbox = SandboxCore(ActionBudget(2, 2, 2, 1))
    asyncio.run(sandbox.reset_world({}))
    asyncio.run(sandbox.execute("agent-1", "set", {"key": "x", "value": 1}, "a-1"))
    with pytest.raises(BudgetExceeded):
        asyncio.run(sandbox.execute("agent-1", "set", {"key": "y", "value": 2}, "a-2"))
