"""Recovery must hash nested roots independently and reject false precision."""
from io import BytesIO
from zipfile import ZipFile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from audit_recovery_boundary import nested_snapshots, observation_time_diagnostic
from scientific_closure import windows_snapshot_hash


def test_nested_source_roots_preserve_all_three_domains_and_ignore_cache():
    files = {"src/ioabench/__init__.py": b"", "contracts/Z.json": b"{}", "config/a.json": b"1"}
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for prefix in ("", "artifacts/old/", "release/old/"):
            for name, data in files.items():
                archive.writestr(prefix + name, data)
            archive.writestr(prefix + "src/ioabench/__pycache__/old.pyc", b"ignored")
        rows = nested_snapshots(archive)
    assert len(rows) == 2
    assert all(r["file_count"] == 3 and r["source_sha256"] == windows_snapshot_hash(files) for r in rows)


def test_observation_time_never_certifies_original_attempt_identity():
    results = {"x": {"status": "COMPLETED", "replay": {"timeline": [{"event_time": "2026-10-01T01:00:00+00:00"}]}}}
    report = observation_time_diagnostic(results, {"tool_time": {"start": 0}})
    assert report["retained_trajectories_starting_later"] == {"COMPLETED": 1}
    assert not report["can_identify_original_invalid_case_ids"]
