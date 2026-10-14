from ioabench.ioa.incentive import IncentiveLedger, IncentiveSignal


def test_incentive_utility_is_not_a_safety_score() -> None:
    ledger = IncentiveLedger()
    ledger.add(IncentiveSignal("agent-1", 2.0, "local", "fast-completion", {"case": "1"}))
    ledger.add(IncentiveSignal("agent-1", 3.0, "global", "task-value", {}))
    assert ledger.utility("agent-1", "local") == 2.0
    assert ledger.utility("agent-1", "global") == 3.0
