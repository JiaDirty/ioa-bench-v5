import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest

from ioabench.v5.dynamic import t331_slice


def script():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/build_history_index.py"
    spec = importlib.util.spec_from_file_location("build_history_index", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_inventory_binds_cases_keeps_nested_gaps_and_never_extracts_secrets(tmp_path):
    path = tmp_path / "archive/retained.zip"
    path.parent.mkdir()
    pair = next(iter(t331_slice.generate(seed=21, families=1)))
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../../pair.json", json.dumps([case.as_dict() for case in pair]))
        archive.writestr(".env", "SECRET=private")
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as inner:
            inner.writestr("cases.json", json.dumps(pair[0].as_dict()))
        archive.writestr("nested.zip", nested.getvalue())
        archive.writestr("broken.zip", b"broken")
        archive.writestr("rejected.json", "invalid json")
    output = tmp_path / "artifacts/index"
    source, report = script().archive_cases(tmp_path, output)
    assert len(source.read_text(encoding="utf-8").splitlines()) == 3
    assert report["case_occurrences"] == 3
    assert {row["code"] for row in report["findings"]} == {"NESTED_ARCHIVE_UNREADABLE", "ARCHIVE_MEMBER_NOT_INDEXABLE"}
    assert any(item["member"] == "nested.zip!cases.json" for item in report["archives"]["archive/retained.zip"]["members"])
    assert not (tmp_path / ".env").exists()
    assert "private" not in source.read_text(encoding="utf-8")
    script().archive_cases(tmp_path, output)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("pair.json", "[]")
    with pytest.raises(ValueError, match="inventory changed"):
        script().archive_cases(tmp_path, output)
