"""Fail-closed evidence inventory for the v5 publication-readiness contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SUITES = (
    "T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
    "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363",
)
CHECKPOINT = "2026-10-09"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def build_audit(root: Path) -> dict[str, Any]:
    construct_path = root / "contracts/v5/construct_maps.json"
    offline_path = root / "artifacts/v5/gates/offline-matrix-20261009-single-model-precheck.json"
    quality_path = root / "artifacts/v5/data_quality/5.1.5-candidate-20261006/report.json"
    diagnostic_path = root / "artifacts/v5/pilot/pilot-20261006-v5.1.5/deepseek_single_model_diagnostic.json"
    review_dir = root / "artifacts/v5/review_package/pilot-20261006-v5.1.5-deepseek-single-model"

    constructs = json.loads(construct_path.read_text(encoding="utf-8"))
    offline = json.loads(offline_path.read_text(encoding="utf-8"))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    offline_ok = (
        len(offline.get("suites", [])) == len(SUITES)
        and sum(item.get("pairs_checked", 0) for item in offline["suites"]) == 3240
        and all(item.get("passed") and not item.get("failures") for item in offline["suites"])
    )
    quality_ok = (
        len(quality.get("suites", [])) == len(SUITES)
        and all(item.get("candidate_gate_failure_count") == 0 for item in quality["suites"])
    )
    construct_ok = set(constructs.get("suites", {})) == set(SUITES)
    suite_files = all(_exists(root, f"src/ioabench/v5/suites/{suite.lower()}.py") for suite in SUITES)

    gates: dict[str, dict[str, Any]] = {
        "A": {
            "status": "CONDITIONAL_AUTOMATED",
            "automated_evidence": construct_ok and suite_files and offline_ok,
            "external_required": True,
            "blockers": ["construct/domain review is not complete"],
        },
        "B": {
            "status": "CONDITIONAL_AUTOMATED",
            "automated_evidence": suite_files,
            "external_required": True,
            "blockers": ["blinded scorer validity and agreement evidence is absent"],
        },
        "C": {
            "status": "AUTOMATED_CANDIDATE_PASS",
            "automated_evidence": quality_ok,
            "external_required": False,
            "blockers": ["candidate data is not frozen as a Release"],
        },
        "D": {
            "status": "BLOCKED_EXTERNAL_REVIEW",
            "automated_evidence": all(_exists(review_dir, name) for name in (
                "MANIFEST.json", "REVIEWER_MANIFEST.json", "REVIEWER_INSTRUCTIONS.md",
                "ADJUDICATION_WORKFLOW.md", "part_a_constructs.md",
            )),
            "external_required": True,
            "blockers": ["two independent human/expert reviewer label sets and agreement reports are absent"],
        },
        "E": {
            "status": "PENDING_APPROVED_CONFIRMATION",
            "automated_evidence": diagnostic.get("formal_model") == "deepseek-v4.1-flash",
            "external_required": True,
            "blockers": ["historical diagnostic is exploratory; 8192-token confirmation Pilot has not run"],
        },
        "F": {"status": "NOT_STARTED", "automated_evidence": False, "external_required": False,
              "blockers": ["Gate D and Gate E are incomplete"]},
        "G": {"status": "NOT_STARTED", "automated_evidence": False, "external_required": True,
              "blockers": ["Release is not frozen and formal Campaign is not authorized"]},
        "H": {"status": "NOT_STARTED", "automated_evidence": False, "external_required": False,
              "blockers": ["no confirmatory results, test-retest, or publication report exist"]},
    }
    return {
        "audit_version": "v5-publication-readiness-audit-1.0.0",
        "checkpoint": CHECKPOINT,
        "formal_model": "deepseek-v4.1-flash",
        "publication_ready": False,
        "reason": "Fail-closed: required Gate D/E/F/G/H evidence is incomplete.",
        "gates": gates,
        "evidence": {
            "construct_maps": {"path": str(construct_path.relative_to(root)), "suite_count": len(constructs.get("suites", {})), "sha256": _sha256(construct_path)},
            "offline_matrix": {"path": str(offline_path.relative_to(root)), "passed": offline_ok, "sha256": _sha256(offline_path)},
            "candidate_quality": {"path": str(quality_path.relative_to(root)), "passed": quality_ok, "sha256": _sha256(quality_path)},
            "deepseek_diagnostic": {"path": str(diagnostic_path.relative_to(root)), "rows": diagnostic.get("rows"), "sha256": _sha256(diagnostic_path)},
            "review_package": str(review_dir.relative_to(root)),
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# IoA-Bench v5 Publication Readiness Audit",
        "",
        f"- Audit: `{report['audit_version']}`",
        f"- Checkpoint: `{report['checkpoint']}`",
        f"- Formal model: `{report['formal_model']}`",
        f"- `PUBLICATION_READY`: **{str(report['publication_ready']).upper()}**",
        f"- Reason: {report['reason']}",
        "",
        "| Gate | Status | Automated evidence | Blocker |",
        "|---|---|---|---|",
    ]
    for gate, item in report["gates"].items():
        lines.append(f"| {gate} | `{item['status']}` | `{item['automated_evidence']}` | {'; '.join(item['blockers'])} |")
    lines += ["", "This report is an evidence inventory, not a substitute for human review or an online confirmation run.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = build_audit(args.root.resolve())
    out = args.out or args.root / "artifacts/v5/publication_readiness/v5-single-model-readiness-20261009.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(_markdown(report), encoding="utf-8")
    print(f"PUBLICATION_READY={report['publication_ready']}; report={out}")


if __name__ == "__main__":
    main()
