from ioabench.runtime.scheduler import WorkScheduler


def test_scheduler_expands_deterministic_case_units() -> None:
    cases = [{"candidate_id": "c1", "provenance": {"condition": "RISK"}}, {"candidate_id": "c2", "provenance": {"condition": "CONTROL"}}]
    scheduler = WorkScheduler()
    first = scheduler.expand("mock", "T311", "1.0.0", cases, repetitions=2)
    second = scheduler.expand("mock", "T311", "1.0.0", cases, repetitions=2)
    assert first == second
    assert len(first) == 4
    assert len({unit.work_id for unit in first}) == 4
