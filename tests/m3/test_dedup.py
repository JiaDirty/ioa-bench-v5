from ioabench.generation.dedup import Deduplicator


def test_deduplicator_rejects_exact_and_near_duplicates_reproducibly() -> None:
    dedup = Deduplicator(near_threshold=0.75)
    assert dedup.add({"text": "Invoice review pending", "world": "W01"})
    assert not dedup.add({"world": "W01", "text": "invoice   review pending"})
    assert not dedup.add({"text": "Invoice review pending now", "world": "W01"})
    assert dedup.add({"text": "Unrelated logistics task", "world": "W04"})
