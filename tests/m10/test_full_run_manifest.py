import json
from pathlib import Path

from ioabench.runtime.full_manifest import FullRunManifest


def test_full_run_manifest_pins_model_datasets_and_runtime(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    builder = FullRunManifest(root)
    manifest = builder.build(run_id="mock-all-v1-test", model_id="deepseek-v4.1-flash")
    assert manifest["tested_model"]["model_id"] == "deepseek-v4.1-flash"
    assert len(manifest["benchmark"]["dataset_versions"]) == 18
    assert manifest["benchmark"]["dataset_versions"]["T311"] == "1.4.0"
    assert manifest["benchmark"]["suite_versions"] == manifest["benchmark"]["dataset_versions"]
    path = builder.freeze(manifest, tmp_path / "manifests")
    assert json.loads(path.read_text(encoding="utf-8"))["run_id"] == "mock-all-v1-test"
