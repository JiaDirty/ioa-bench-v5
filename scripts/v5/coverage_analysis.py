"""M8 pre-argumentation: per-suite coverage analysis of the frozen candidate data.

Scans the frozen v5 candidate datasets (5.1.5-candidate-20261006 baseline plus the T332 5.1.6
local candidate) and computes, per suite: subtype, difficulty, domain, arm and evidence-carrier
coverage; the dynamic-world structural families present; and the gap cells a scaled generation
campaign (M8) would need to fill. Offline only — no provider calls, no case mutation.

Output: artifacts/v5/dynamic_world/coverage-analysis.json (refuses overwrite).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.core.case import case_from_dict  # noqa: E402
from ioabench.v5.dynamic.signature import signature, structural_delta  # noqa: E402
from ioabench.v5.suites import SUITE_MODULES  # noqa: E402

DATASET_DIR = ROOT / "data/v5/datasets"
BASELINE = "5.1.5-candidate-20261006"
T332_LOCAL = "5.1.6-candidate-20261009"
DEST = ROOT / "artifacts/v5/dynamic_world/coverage-analysis.json"


def suite_cases(suite_id: str) -> list[dict]:
    version = T332_LOCAL if suite_id == "T332" else BASELINE
    path = DATASET_DIR / suite_id / version / "cases.jsonl"
    cases = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                cases.append(case_from_dict(json.loads(line)))
    return cases


def main() -> int:
    if DEST.exists():
        print(f"REFUSED: {DEST} exists", file=sys.stderr)
        return 1
    suites = {}
    classic_pairs = {}
    for suite_id in SUITE_MODULES:
        cases = suite_cases(suite_id)
        classic = __import__(f"ioabench.v5.suites.{suite_id.lower()}", fromlist=["generate"])
        classic_pair = classic.generate(seed=5, families=1)[0]
        classic_pairs[suite_id] = {"control": classic_pair[0], "risk": classic_pair[1]}
        subtypes = Counter(c.subtype for c in cases)
        difficulties = Counter(c.difficulty for c in cases)
        domains = Counter(c.domain for c in cases)
        families = sorted({c.family_id for c in cases})
        carriers = Counter(tuple(sorted(c.fingerprints)) for c in cases)
        # dynamic-world family separation: each classic case vs the classic pair of other suites
        classic_sig = signature(classic_pairs[suite_id]["control"].as_dict())
        suites[suite_id] = {
            "dataset_version": T332_LOCAL if suite_id == "T332" else BASELINE,
            "cases": len(cases),
            "pairs": len(cases) // 2,
            "subtypes": dict(sorted(subtypes.items())),
            "difficulties": dict(sorted(difficulties.items())),
            "domains": dict(sorted(domains.items())),
            "families": len(families),
            "carrier_shapes": len(carriers),
            "classic_signature_digest": classic_sig,
        }
    # cross-suite family overlap on classic structure
    overlap = []
    ids = sorted(classic_pairs)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            delta = structural_delta(signature(classic_pairs[a]["control"].as_dict()),
                                     signature(classic_pairs[b]["control"].as_dict()))
            if not delta["same_family"]:
                overlap.append({"suites": [a, b], "dimensions": delta["dimensions"]})
    # gap cells: subtype × difficulty emptiness inside each suite's own frame
    gap_cells = {}
    for suite_id, data in suites.items():
        gaps = []
        st_count = len(data["subtypes"])
        for subtype in sorted({c.subtype for c in ()}) or []:
            pass
        # a cell is a gap only if the suite's own design declares the subtype but the
        # difficulty stratum is thin (fewer than the design target share)
        total = data["cases"]
        for subtype, count in sorted(data["subtypes"].items()):
            share = count / max(total, 1)
            if share < 0.10:  # each declared subtype should hold ~1/5 or ~1/9 of the suite
                gaps.append({"subtype": subtype, "cases": count, "share": round(share, 3)})
        diff_gaps = [d for d, n in data["difficulties"].items() if n < total * 0.2]
        if diff_gaps:
            gaps.append({"difficulty_thin": diff_gaps})
        gap_cells[suite_id] = gaps or "none"
    result = {
        "kind": "ioabench.v5.dynamic-world.coverage-analysis/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline": BASELINE,
        "t332_local": T332_LOCAL,
        "note": ("M8 pre-argumentation evidence: coverage of the frozen candidate data per suite, "
                 "computed offline; a scaled generation campaign needs PI approval (PI-V5-007) and "
                 "these gap cells pre-argue what it should fill"),
        "suites": suites,
        "cross_suite_family_distinctness": {"distinct_pairs": len(overlap), "examples": overlap[:6]},
        "gap_cells": gap_cells,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK suites={len(suites)} -> {DEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
