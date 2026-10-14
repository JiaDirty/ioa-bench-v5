"""DW-AUDIT-011 preparation: audit-ready material packages for the two pre-registered audits
that remain on the PI path (T331 utility attribution; T333 scorer abstention).

This script ONLY gathers and organizes existing evidence into review-ready packages:
  * the pilot rows for the suite (from the historical 2026-10-06 pilot, read-only);
  * the corresponding frozen cases;
  * the pre-registered norms / scorer rules verbatim from the construct map and scorer source;
  * a README stating what the auditor judges — WITHOUT suggesting answers.

The audit JUDGMENT itself is not performed here: it remains on the PI/expert path per the work
queue (DW-AUDIT-011). No scorer, construct, or threshold is touched.
Output: artifacts/v5/dynamic_world/audit-prep/{T331,T333}-*/ (refuses overwrite).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.core.case import case_from_dict  # noqa: E402
from ioabench.v5.suites import load as load_suite  # noqa: E402

PILOT_RESULTS = ROOT / "artifacts/v5/pilot/pilot-20261006-v5.1.5/results.jsonl"
PILOT_DIR = ROOT / "artifacts/v5/pilot/pilot-20261006-v5.1.5"
CASES_DIR = ROOT / "data/v5/datasets"
OUT_BASE = ROOT / "artifacts/v5/dynamic_world/audit-prep"

SPECS = {
    "T331": {
        "audit_name": "utility-shortfall-attribution",
        "question": ("Why does the utility fall short on BOTH arms (33/48 TASK_SAFE_BUT_FAILED "
                     "vs 14/48 EARLY_SAFE) — is it a scenario path defect, a runner/tool gap, or "
                     "genuine model non-completion? No scorer edits."),
        "norms_from_construct_map": ["task_utility", "norms", "recovery", "exclusions"],
    },
    "T333": {
        "audit_name": "scorer-abstention-audit",
        "question": ("Is the pre-registered free-text abstain rule (28/48 SCORER_ABSTAINED) "
                     "behaving as intended, or is the lexicon band mis-drawn? No scorer edits."),
        "norms_from_construct_map": ["norms", "task_utility", "boundary_examples"],
    },
}


def rows_for(suite_id: str) -> list[dict]:
    rows = []
    with PILOT_RESULTS.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("suite_id") == suite_id:
                rows.append(entry)
    return rows


def cases_for(suite_id: str, case_ids: set[str]) -> list[dict]:
    version = "5.1.6-candidate-20261009" if suite_id == "T332" else "5.1.5-candidate-20261006"
    path = CASES_DIR / suite_id / version / "cases.jsonl"
    out = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            case = case_from_dict(json.loads(line))
            if case.case_id in case_ids:
                out.append(case.as_dict())
    return out


def build_package(suite_id: str) -> Path:
    spec = SPECS[suite_id]
    classic = load_suite(suite_id)
    construct = json.loads((ROOT / "contracts/v5/construct_maps.json").read_text(encoding="utf-8"))
    cm = construct["suites"][suite_id]
    rows = rows_for(suite_id)
    case_ids = {r.get("case_id") for r in rows}
    frozen_cases = cases_for(suite_id, case_ids)
    run_dir = OUT_BASE / f"{suite_id}-{spec['audit_name']}"
    if run_dir.exists():
        raise SystemExit(f"REFUSED: {run_dir} exists")
    run_dir.mkdir(parents=True)

    (run_dir / "pilot_rows.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8")
    (run_dir / "frozen_cases.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in frozen_cases) + "\n",
        encoding="utf-8")
    (run_dir / "pre_registered_construct_excerpt.json").write_text(
        json.dumps({k: cm[k] for k in cm if k in
                    ("norms", "task_utility", "recovery", "canonical_question", "mechanism_subtypes",
                     "difficulty", "exclusions", "boundary_examples") or k.startswith("canonical")},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    # the pre-registered scorer source, verbatim (audit judges the rule as-is)
    scorer_src = Path(classic.__file__).read_text(encoding="utf-8")
    (run_dir / "scorer_source_verbatim.py").write_text(scorer_src, encoding="utf-8")
    readme = (
        f"# {suite_id} audit package (DW-AUDIT-011 preparation)\n\n"
        f"Created: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n"
        f"## Audit question (for the auditor to judge — no answer is suggested here)\n\n"
        f"{spec['question']}\n\n"
        f"## Contents\n\n"
        f"- pilot_rows.jsonl — the 2026-10-06 historical pilot rows for {suite_id} (read-only copy)\n"
        f"- frozen_cases.jsonl — the corresponding frozen candidate cases\n"
        f"- pre_registered_construct_excerpt.json — the construct-map fields governing this audit\n"
        f"- scorer_source_verbatim.py — the pre-registered scorer source, verbatim\n\n"
        f"## Boundaries\n\n"
        f"- The audit JUDGMENT is performed by the PI/expert path, not by this package.\n"
        f"- No scorer, construct, threshold, or norm was changed to produce this package.\n"
        f"- Outcome-driven scorer edits remain prohibited (work queue DW-AUDIT-011).\n")
    (run_dir / "README.md").write_text(readme, encoding="utf-8")
    return run_dir


def main() -> int:
    created = []
    for suite_id in ("T331", "T333"):
        created.append(str(build_package(suite_id).relative_to(ROOT)))
    record = {
        "kind": "ioabench.v5.dynamic-world.audit-prep/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": "DW-AUDIT-011 preparation (materials only; judgment remains on the PI/expert path)",
        "packages": created,
        "boundaries": "no scorer/construct/threshold changes; no audit judgment performed here",
    }
    (OUT_BASE / "audit-prep-record.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK packages={len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
