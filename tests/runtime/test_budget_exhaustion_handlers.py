import ast
from pathlib import Path


RUNTIME = Path(__file__).parents[2] / "src/ioabench/runtime"


def test_every_runtime_tool_budget_has_a_terminal_handler():
    missing = []
    for path in RUNTIME.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        consumes_budget = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "consume_tool_call"
            for node in ast.walk(tree)
        )
        handles_budget = any(
            isinstance(node, ast.ExceptHandler)
            and (
                isinstance(node.type, ast.Name) and node.type.id == "BudgetExceeded"
                or isinstance(node.type, ast.Tuple)
                and any(isinstance(item, ast.Name) and item.id == "BudgetExceeded" for item in node.type.elts)
            )
            for node in ast.walk(tree)
        )
        if consumes_budget and not handles_budget:
            missing.append(path.name)
    assert missing == []
