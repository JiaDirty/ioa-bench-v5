"""Check current handoff packaging without touching real data or calling providers."""
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


@pytest.fixture
def packager(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("current_source_review", scripts / "package_chatgpt_review.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.pack, "ROOT", tmp_path)
    monkeypatch.setattr(module, "EVIDENCE", {"artifacts/required.json"})
    for number in (311,312,313,321,322,323,331,332,333,341,342,343,351,352,353,361,362,363):
        path = tmp_path / f"src/ioabench/v5/suites/t{number}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# source fixture\n", encoding="utf-8")
    for name, content in {"docs/HANDOFF_CURRENT.md":"Current scope\n", "artifacts/required.json":"{}",
                          ".env":"API_KEY=private-fixture-value", "archive/old.txt":"old",
                          "data/runs/private.txt":"history", "exports/old/old.txt":"old"}.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return module, tmp_path


def test_build_binds_current_handoff_and_preserves_old_output(packager):
    module, root = packager
    output = root / "exports/current"
    module.main(output, root / "docs/HANDOFF_CURRENT.md", snapshot_metadata={"source_git_head": "fixed-test-head"})
    result = json.loads((output / "PACKAGE_VERIFICATION.json").read_text())
    assert result["all_file_sha256_match"] and result["secret_scan"] == "PASS"
    with zipfile.ZipFile(output / result["archive"]) as archive:
        snapshot = json.loads(archive.read(module.pack.META + "SNAPSHOT.json"))
        assert snapshot["read_first"] == "docs/HANDOFF_CURRENT.md"
        assert snapshot["source_git_head"] == "fixed-test-head"
        assert module.pack.PREFIX + "artifacts/required.json" in archive.namelist()
        assert not any(name.endswith((".env", "old.txt", "private.txt")) for name in archive.namelist())
    with pytest.raises(FileExistsError):
        module.main(output, root / "docs/HANDOFF_CURRENT.md")
    assert (root / "exports/old/old.txt").read_text() == "old"


def test_credentials_in_source_are_rejected_before_publication(packager):
    module, root = packager
    (root / "docs/leak.md").write_bytes(b"sk-" + b"Q" * 28)
    with pytest.raises(AssertionError, match="Credential detected"):
        module.main(root / "exports/leak", root / "docs/HANDOFF_CURRENT.md")
    assert not list((root / "exports/leak").glob("*.zip"))


def test_missing_evidence_is_not_silently_omitted(packager):
    module, root = packager
    (root / "artifacts/required.json").unlink()
    with pytest.raises(AssertionError, match="Required evidence missing"):
        module.main(root / "exports/missing", root / "docs/HANDOFF_CURRENT.md")


def test_output_and_handoff_paths_are_bounded(packager):
    module, root = packager
    with pytest.raises(ValueError, match="Output must"):
        module.main(root.parent / "outside", root / "docs/HANDOFF_CURRENT.md")
    with pytest.raises(ValueError, match="Handoff must"):
        module.main(root / "exports/missing-handoff", root / "missing.md")
    assert not (root / "exports/missing-handoff").exists()
