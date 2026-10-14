"""Fine-grained mechanism-slot diff analysis over the frozen 5.1.5 candidate data
(post-audit amendment "其他负控": within-slot sub-field confound check, report-only).

For every CONTROL/RISK pair in the frozen candidate datasets this computes the LEAF-LEVEL
diff paths inside each declared mechanism slot and aggregates, per suite, the complete set of
leaf paths that vary. Purpose: expose any within-slot variation that carries extra confounds
(difficulty/label carriers, unrelated evidence fields) beyond the suite's pre-registered
mechanism intent. READ-ONLY over the frozen data — nothing is modified.

The per-suite empirical leaf-path inventory is exactly the sub-field whitelist the dynamic
slices enforce via fine_arm_delta; running it over the frozen data shows how much narrower the
classic coarse slots are in practice, and flags suites whose slots hide confound carriers.

Output: artifacts/v5/dynamic_world/fine-slot-diff-analysis.json (refuses overwrite).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.core.case import case_from_dict, json_diff_paths  # noqa: E402
from ioabench.v5.suites import SUITE_MODULES  # noqa: E402

DATASET_DIR = ROOT / "data/v5/datasets"
BASELINE = "5.1.5-candidate-20261006"
T332_LOCAL = "5.1.6-candidate-20261009"
DEST = ROOT / "artifacts/v5/dynamic_world/fine-slot-diff-analysis.json"

# leaf path fragments that would indicate a confound carrier inside a mechanism slot
CONFOUND_MARKERS = ("difficulty", "threshold", "quota", "budget", "deadline_days")


def leaf_diffs_within_slot(control: dict, risk: dict, slot: str) -> list[str]:
    """Leaf diff paths between control/risk worlds, restricted to one mechanism slot subtree."""
    def get(doc: dict, pointer: str):
        current = doc
        for token in pointer.lstrip("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and token in current:
                current = current[token]
            elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
                current = current[int(token)]
            else:
                return None
        return current

    c_sub, r_sub = get(control, slot), get(risk, slot)
    if c_sub is None or r_sub is None:
        return ["<slot unresolvable>"]
    prefix = slot.rstrip("/")
    return [prefix + p for p in json_diff_paths(c_sub, r_sub)]


def main() -> int:
    if DEST.exists():
        print(f"REFUSED: {DEST} exists", file=sys.stderr)
        return 1
    suites = {}
    for suite_id in SUITE_MODULES:
        version = T332_LOCAL if suite_id == "T332" else BASELINE
        path = DATASET_DIR / suite_id / version / "cases.jsonl"
        cases = []
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if line:
                    cases.append(case_from_dict(json.loads(line)))
        by_pair: dict[str, dict[str, dict]] = {}
        for case in cases:
            by_pair.setdefault(case.pair_id, {})[case.arm] = case.as_dict()
        slot_paths: dict[str, set] = defaultdict(set)
        confound_hits: list[dict] = []
        slot_count = None
        uniform_slots = True
        for pair_id, arms in sorted(by_pair.items()):
            if set(arms) != {"CONTROL", "RISK"}:
                continue
            control, risk = arms["CONTROL"], arms["RISK"]
            slots = control.get("mechanism_slots", [])
            if slot_count is None:
                slot_count = len(slots)
            elif len(slots) != slot_count:
                uniform_slots = False
            for slot in slots:
                paths = leaf_diffs_within_slot(control, risk, slot)
                for p in paths:
                    slot_paths[slot].add(p)
                    lowered = p.lower()
                    if any(m in lowered for m in CONFOUND_MARKERS):
                        confound_hits.append({"pair_id": pair_id, "path": p})
        suites[suite_id] = {
            "dataset_version": version,
            "pairs": sum(1 for arms in by_pair.values() if set(arms) == {"CONTROL", "RISK"}),
            "slots": {slot: {"varying_leaf_paths": sorted(paths),
                             "distinct_leaf_path_count": len(paths)}
                      for slot, paths in sorted(slot_paths.items())},
            "confound_marker_hits": confound_hits,
            "uniform_slot_count_across_pairs": uniform_slots,
        }
    result = {
        "kind": "ioabench.v5.dynamic-world.fine-slot-diff-analysis/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline": BASELINE,
        "t332_local": T332_LOCAL,
        "note": ("report-only analysis of the frozen candidate data; the per-suite varying-leaf-path "
                 "inventory is the empirical sub-field whitelist that fine_arm_delta whitelists in "
                 "the dynamic slices enforce by construction; confound markers flag any within-slot "
                 "variation carrying difficulty/threshold/quota/budget/deadline carriers"),
        "suites": suites,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    flagged = sum(1 for s in suites.values() if s["confound_marker_hits"])
    print(f"OK suites={len(suites)} flagged={flagged} -> {DEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
