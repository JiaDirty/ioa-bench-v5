"""A layout migration must preserve old frozen-baseline identities."""
import importlib.util
from pathlib import Path


def test_historical_archive_lookup_keeps_original_file_precedence(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "scripts/scientific_closure.py"
    spec = importlib.util.spec_from_file_location("workspace_scientific_closure", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archive = tmp_path / "archive/deliveries"
    archive.mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "ARCHIVE_DIR", archive)
    name = "IoA-Bench-history.zip"
    (archive / name).write_bytes(b"preserved")
    assert module.baseline_path(name) == archive / name
    (tmp_path / name).write_bytes(b"original")
    assert module.baseline_path(name) == tmp_path / name
    assert module.baseline_path("data/result.zip") == tmp_path / "data/result.zip"
    assert module.baseline_path(".env") == tmp_path / ".env"
