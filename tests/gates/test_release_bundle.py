import json
from pathlib import Path

from ioabench.release import build_bundle


def test_release_bundle_excludes_credentials(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    run_id = "deepseek-v4.1-flash-v1-pack-v2-r5"
    bundle = build_bundle(root, run_id, tmp_path / "release")
    manifest = json.loads((bundle / "bundle-manifest.json").read_text(encoding="utf-8"))
    m9 = json.loads((root / "artifacts" / "gates" / "M9.json").read_text(encoding="utf-8"))
    assert manifest["provider_credentials_included"] is False
    assert not list(bundle.rglob("*.env"))
    assert (bundle / "environment.json").exists()
    assert manifest["file_count"] > 0
    assert (bundle / "src" / "ioabench" / "cli.py").exists()
    assert (bundle / "tests").is_dir()
    assert manifest["run_id"] == run_id
    assert (bundle / "data" / "datasets" / "DATASET_PACK_v2.yaml").exists()
    assert (bundle / "artifacts" / "gates" / "FINAL_SCIENTIFIC_ACCEPTANCE.json").exists()
    for suite, evidence in m9["evidence"].items():
        assert (bundle / "data" / "datasets" / suite / evidence["version"]).is_dir()
