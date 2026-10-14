from pathlib import Path

import yaml

from tests.formal_dataset_support import SUITES, load_formal


def test_formal_dataset_pack_manifest_pins_all_versions_and_hashes() -> None:
    root = Path(__file__).parents[2]
    value = {"pack": "DATASET_PACK_v1", "immutable": True, "suites": {}}
    for suite in SUITES:
        manifest, _ = load_formal(root, suite)
        value["suites"][suite] = {"version": manifest["version"], "content_sha256": manifest["content_sha256"], "generator_version": manifest["generation"]["generator_version"]}
    path = root / "data" / "datasets" / "DATASET_PACK_v1.yaml"
    serialized = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    if path.exists():
        assert path.read_text(encoding="utf-8") == serialized
    else:
        path.write_text(serialized, encoding="utf-8")
    assert len(value["suites"]) == 18
