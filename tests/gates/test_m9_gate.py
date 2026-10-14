import json
from pathlib import Path

import yaml

from tests.formal_dataset_support import SUITES, load_formal


def test_m9_gate_records_formal_frozen_datasets() -> None:
    root = Path(__file__).parents[2]
    pack = yaml.safe_load((root / "data" / "datasets" / "DATASET_PACK_v1.yaml").read_text(encoding="utf-8"))
    evidence = {suite: {"version": load_formal(root, suite)[0]["version"], "case_count": len(load_formal(root, suite)[1]), "content_sha256": pack["suites"][suite]["content_sha256"]} for suite in SUITES}
    semantic_states = {item["quality_gates"]["semantic_validation"] for suite in SUITES for item in [load_formal(root, suite)[0]]}
    status = "PASS" if semantic_states == {"DUAL_VALIDATOR"} else "BLOCKED_SEMANTIC_VALIDATION"
    artifact = {"gate": "M9", "status": status, "returncode": 0 if status == "PASS" else 2, "total_cases": sum(item["case_count"] for item in evidence.values()), "evidence": evidence, "semantic_validation_states": sorted(semantic_states)}
    path = root / "artifacts" / "gates" / "M9.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert artifact["total_cases"] == 1620 and artifact["status"] == "PASS"
