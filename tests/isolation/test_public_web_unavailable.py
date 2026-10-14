import pytest

from ioabench.security import FormalToolPolicy, PublicWebUnavailable


def test_formal_tool_policy_denies_public_web() -> None:
    policy = FormalToolPolicy()

    with pytest.raises(PublicWebUnavailable):
        policy.check("mcp", "https://example.com")
    with pytest.raises(PermissionError):
        policy.check("browser")
