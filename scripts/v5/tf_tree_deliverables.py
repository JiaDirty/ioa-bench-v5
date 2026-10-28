"""Emit the M2 tree deliverables: TREE_SPEC.json and TREE_SELECTION_RECEIPTS.jsonl."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"


def main() -> int:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree

    tree = ScenarioBranchTree()
    spec = tree.spec()
    (OUT / "TREE_SPEC.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    receipts, cells = [], set()
    for seed in (5, 11, 101, 2027):
        for industry in ("industry.medicine_supply", "industry.payment_clearing"):
            selection = tree.select(seed=seed, industry=industry)
            receipt = {"seed": seed, "industry": industry,
                       "industry_probabilities": selection["industry_probabilities"],
                       "requested_obligations": selection["obligations"],
                       "resolved": {key: selection[key] for key in
                                    ("obligations", "roles", "assets", "tools", "stages",
                                     "evidence_sources", "events", "coverage_cells",
                                     "selected_node_sha256")},
                       "mechanism_binding": tree.bind_mechanism_slots(selection),
                       "selection_sha256": canonical_sha256(selection)}
            receipts.append(receipt)
            cells.update(selection["coverage_cells"])
    with (OUT / "TREE_SELECTION_RECEIPTS.jsonl").open("w", encoding="utf-8") as stream:
        for receipt in receipts:
            stream.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    coverage = tree.coverage_gaps(cells)
    (OUT / "TREE_COVERAGE.json").write_text(
        json.dumps({"planned_selections": len(receipts), "coverage": coverage,
                    "provider_calls": 0}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"receipts": len(receipts), "cells": coverage["produced_cells"],
                      "missing": coverage["missing_cells"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
