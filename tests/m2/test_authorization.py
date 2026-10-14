from ioabench.ioa.authorization import AuthorizationDecision, LocalAuthorizer
from ioabench.ioa.delegation import DelegationGraph


def test_authorization_distinguishes_allow_deny_indeterminate_and_error() -> None:
    graph = DelegationGraph()
    delegation = graph.create(issuer="a", subject="b", resource="invoice", action_scope=frozenset({"read"}), audience=frozenset({"org-b"}), delegation_id="d-1")
    authorizer = LocalAuthorizer(graph)

    assert authorizer.authorize(subject="b", resource="invoice", action="read", audience="org-b", delegation_id="d-1").decision is AuthorizationDecision.ALLOW
    assert authorizer.authorize(subject="b", resource="invoice", action="write", audience="org-b", delegation_id="d-1").decision is AuthorizationDecision.DENY
    assert authorizer.authorize(subject="b", resource="invoice", action="read", audience="org-b", delegation_id=None).decision is AuthorizationDecision.INDETERMINATE
    assert authorizer.authorize(subject="b", resource="invoice", action="read", audience="org-b", delegation_id="missing").decision is AuthorizationDecision.ERROR
