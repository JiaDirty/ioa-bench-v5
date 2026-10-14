from pathlib import Path

from ioabench.runtime import CheckpointStore


def test_checkpoint_survives_new_store_instance(tmp_path: Path) -> None:
    first = CheckpointStore(tmp_path / "checkpoints")
    first.save("run-1", {"case_index": 3, "status": "RUNNING"})

    second = CheckpointStore(tmp_path / "checkpoints")
    assert second.load("run-1") == {"case_index": 3, "status": "RUNNING"}
