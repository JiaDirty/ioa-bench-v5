import pytest

from ioabench.ioa.delegation import DelegationGraph


def test_delegation_enforces_child_scope_and_parent_depth() -> None:
    graph = DelegationGraph()
    parent = graph.create(issuer="a", subject="b", resource="invoice", action_scope=frozenset({"read", "write"}), audience=frozenset({"org-b"}), max_depth=1, delegation_id="d-parent")
    child = graph.create(issuer="b", subject="c", resource="invoice", action_scope=frozenset({"read"}), audience=frozenset({"org-c"}), parent_id=parent.delegation_id, delegation_id="d-child")

    assert child.max_depth == 0
    with pytest.raises(ValueError, match="exceeds parent"):
        graph.create(issuer="b", subject="c", resource="invoice", action_scope=frozenset({"delete"}), audience=frozenset(), parent_id=parent.delegation_id)
