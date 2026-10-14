from ioabench.runtime.batch import BatchRunner
from ioabench.runtime.scheduler import WorkScheduler


def test_batch_resume_skips_completed_units(tmp_path) -> None:
    units = WorkScheduler().expand("mock", "T311", "1.0.0", [{"candidate_id": "c1", "provenance": {"condition": "RISK"}}])
    calls = []
    runner = BatchRunner(tmp_path / "checkpoint.json")
    first = runner.run(units, lambda unit: calls.append(unit.case_id) or {"status": "COMPLETED", "score": 1.0})
    second = runner.run(units, lambda unit: calls.append("rerun") or {"status": "COMPLETED"})
    assert first[units[0].work_id]["status"] == "COMPLETED"
    assert second == first
    assert calls == ["c1"]
