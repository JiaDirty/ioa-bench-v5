from ioabench.runtime.batch import BatchRunner


def test_batch_runner_marks_unclassified_executor_errors_terminal(tmp_path) -> None:
    from ioabench.runtime.scheduler import WorkScheduler

    units = WorkScheduler().expand("mock", "T311", "1.0.0", [{"candidate_id": "c1", "provenance": {"condition": "RISK"}}])
    state = BatchRunner(tmp_path / "checkpoint.json").run(units, lambda unit: 1 / 0)
    assert state[units[0].work_id]["status"] == "FAILED"
