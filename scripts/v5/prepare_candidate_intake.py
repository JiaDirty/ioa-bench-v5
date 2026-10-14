"""Promote an accepted experimental pair run into replayable v5 intake cases.

This is a local, append-only handoff step. It does not generate, freeze, or scientifically
accept data; it rechecks accepted CONTROL/RISK pairs and writes the standard Case JSONL that
the existing evaluator and blinded-review tooling consume.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.core.case import case_from_dict, pair_diff_violations  # noqa: E402
from ioabench.v5.dynamic import registry  # noqa: E402
from ioabench.v5.dynamic.gates import check_pair_dynamic  # noqa: E402
from ioabench.v5.dynamic.runner import _resolve_scenario  # noqa: E402


INTAKE_VERSION = "ioabench.v5.candidate-intake/1.0.0"


class IntakeRejected(ValueError):
    """The source run is not safe to hand to the evaluator."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def _source_files(source: Path) -> dict[str, str]:
    names = ("manifest.json", "cases.jsonl", "rejected.jsonl", "diversity_report.json")
    return {name: _sha(source / name) for name in names if (source / name).is_file()}


def _load_source(source: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    if not source.is_dir():
        raise IntakeRejected(f"source run does not exist: {source}")
    manifest_path = source / "manifest.json"
    cases_path = source / "cases.jsonl"
    if not manifest_path.is_file() or not cases_path.is_file():
        raise IntakeRejected("source run must contain manifest.json and cases.jsonl")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate_class") != "CANDIDATE_EXPERIMENTAL":
        raise IntakeRejected("only CANDIDATE_EXPERIMENTAL runs may enter this intake")
    rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if manifest.get("pairs_accepted") != len(rows):
        raise IntakeRejected("manifest pair count does not match accepted pair rows")
    return manifest, rows, _source_files(source)


def _check_pair(entry: Mapping[str, Any], index: int) -> tuple[Any, Any, dict[str, Any]]:
    if entry.get("gate_passed") is not True:
        raise IntakeRejected(f"accepted row {index} is missing gate_passed=true")
    try:
        control = case_from_dict(entry["control"], allow_dynamic=True)
        risk = case_from_dict(entry["risk"], allow_dynamic=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise IntakeRejected(f"accepted row {index} contains an invalid case: {exc}") from exc
    if control.suite_id != risk.suite_id or control.pair_id != risk.pair_id:
        raise IntakeRejected(f"accepted row {index} has mismatched suite/pair identity")
    if {control.arm, risk.arm} != {"CONTROL", "RISK"}:
        raise IntakeRejected(f"accepted row {index} is not a CONTROL/RISK pair")
    if pair_diff_violations(control, risk):
        raise IntakeRejected(f"accepted row {index} changes undeclared visible fields")
    try:
        module = registry.get_adapter(control.suite_id)
        scenario = _resolve_scenario(module)
        gate = check_pair_dynamic(control, risk, scenario=scenario, scorer=module.score,
                                  policies=module.policies(), expected=module.EXPECTED_REFERENCE,
                                  fine_arm_delta=module.fine_arm_delta)
    except (KeyError, AttributeError, ValueError) as exc:
        raise IntakeRejected(f"accepted row {index} cannot be rechecked: {exc}") from exc
    if not gate.get("passed"):
        raise IntakeRejected(f"accepted row {index} failed recheck: {gate.get('failures', [])}")
    return control, risk, gate


def prepare_intake(source: Path, output: Path) -> dict[str, Any]:
    """Create a new standard Case JSONL intake directory or fail closed."""
    if output.exists():
        raise IntakeRejected(f"intake output already exists; choose a new versioned path: {output}")
    manifest, rows, source_files = _load_source(source)
    if not rows:
        raise IntakeRejected("source run has no accepted pairs")

    cases: list[Any] = []
    gates: list[dict[str, Any]] = []
    seen_pairs: set[str] = set()
    seen_cases: set[str] = set()
    for index, entry in enumerate(rows):
        control, risk, gate = _check_pair(entry, index)
        if control.pair_id in seen_pairs:
            raise IntakeRejected(f"duplicate pair_id: {control.pair_id}")
        if control.case_id in seen_cases or risk.case_id in seen_cases:
            raise IntakeRejected(f"duplicate case_id in pair: {control.pair_id}")
        seen_pairs.add(control.pair_id)
        seen_cases.update((control.case_id, risk.case_id))
        cases.extend((control, risk))
        gates.append({"pair_id": control.pair_id, "passed": True,
                      "failures": gate.get("failures", []),
                      "control_sha256": control.content_sha256(),
                      "risk_sha256": risk.content_sha256()})

    output.mkdir(parents=True)
    cases_path = output / "cases.jsonl"
    with cases_path.open("x", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            stream.write(json.dumps(case.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    for name in ("rejected.jsonl", "diversity_report.json"):
        source_file = source / name
        if source_file.is_file():
            (output / f"source_{name}").write_bytes(source_file.read_bytes())

    suite_ids = sorted({case.suite_id for case in cases})
    report = {
        "intake_version": INTAKE_VERSION,
        "status": "ENGINEERING_INTAKE_READY",
        "candidate_class": "CANDIDATE_EXPERIMENTAL",
        "formal_accepted": False,
        "provider_calls": 0,
        "source_run": str(source.resolve()),
        "source_manifest": manifest,
        "source_files_sha256": source_files,
        "suite_ids": suite_ids,
        "pairs": len(seen_pairs),
        "cases": len(cases),
        "families": sorted({case.family_id for case in cases}),
        "difficulty_counts": dict(sorted(Counter(case.difficulty for case in cases).items())),
        "subtype_counts": dict(sorted(Counter(case.subtype for case in cases).items())),
        "case_sha256": [case.content_sha256() for case in cases],
        "cases_sha256": _sha(cases_path),
        "pair_gate_rechecks": gates,
        "quality_scope": "Local schema/pair-gate intake only; no semantic model audit, Gate C/D, freeze or formal denominator.",
    }
    _atomic_json(output / "INTAKE_REPORT.json", report)
    _atomic_json(output / "MANIFEST.json", {
        "kind": INTAKE_VERSION,
        "status": report["status"],
        "source_run": report["source_run"],
        "source_manifest_sha256": _sha(source / "manifest.json"),
        "cases_sha256": report["cases_sha256"],
        "pairs": report["pairs"],
        "cases": report["cases"],
        "formal_accepted": False,
        "provider_calls": 0,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare_intake(args.source.resolve(), args.out.resolve())
    except IntakeRejected as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: report[key] for key in ("status", "suite_ids", "pairs", "cases", "cases_sha256")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
