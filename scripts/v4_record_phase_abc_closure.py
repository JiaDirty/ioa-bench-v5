"""Record the Phase A-C closure state for the v4 campaign.

Captures: the offline verification results, the frozen release and manifests,
the workspace-integrity handling for test-written gate artifacts, and the
provider-approval pause point.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, reference, write_new

ART = ROOT / "artifacts/scientific_closure_v4"
GATES = ROOT / "artifacts/gates"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    release_path = ROOT / "release/BENCHMARK_RELEASE_v4-corrective-20261001.json"
    state = yaml.safe_load((ROOT / "state/PROJECT_STATE.yaml").read_text(encoding="utf-8"))

    record = {
        "artifact": "V4_PHASE_ABC_CLOSURE",
        "version": "1",
        "provider_calls": 0,
        "offline_phases_complete": ["A candidate strict retry", "B offline verification", "C release + manifest freeze"],
        "release": reference(release_path),
        "release_id": json.loads(release_path.read_text(encoding="utf-8"))["release_id"],
        "candidate_source_tree_sha256": json.loads(release_path.read_text(encoding="utf-8"))["source_tree_sha256"],
        "verification": {
            "candidate_validation_checks": 82,
            "strict_retry_selfcheck_checks": 23,
            "v4_tests": "22 passed (own pytest process; targets the candidate tree)",
            "workspace_tests": "831 passed, 2 skipped (ignoring tests/v4)",
            "baseline": "19606 protected files unchanged",
            "mock_e2e": "90-case T311 mock suite via the candidate CLI: 90/90 COMPLETED, 90 attempt journals",
        },
        "commands": {
            "candidate_validation": "python -B -X utf8 scripts/validate_corrective_candidate_v4.py --candidate artifacts/scientific_closure_v4/corrective-candidate-v2 --output <new file>",
            "strict_retry_selfcheck": "python -B -X utf8 scripts/v4_selfcheck_strict_retry.py",
            "v4_tests": "python -B -X utf8 -m pytest tests/v4 -q",
            "workspace_tests": "python -B -X utf8 -m pytest tests --ignore=tests/v4 -q",
            "baseline": "python -B -X utf8 scripts/scientific_closure.py verify-baseline",
            "mock_e2e": "python -B -X utf8 scripts/v4_e2e_mock_suite.py",
        },
        "known_operational_notes": [
            "The repository test suite writes artifacts/gates/M*.json, artifacts/suite-gates/T*.json, "
            "artifacts/generation/smoke-report.json and artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json with mock data. "
            "Those are frozen historical evidence, so scripts/v4_restore_overwritten_artifacts.py restores them byte-exactly "
            "from the archives after any test/mock run. Verified twice this session.",
            "tests/v4 targets the v4 candidate source tree and must run as its own pytest invocation; the workspace "
            "ioabench is an editable install frozen at v3.2.",
        ],
        "gate_state": {
            "V4-S0": "PASS (reconcile)", "V4-S1": "PASS", "V4-S2": "PASS", "V4-S3": "PASS", "V4-S4": "PASS",
            "V4-S5": "PASS (release frozen)", "V4-S6": "PASS (18 manifests, identical binding)",
            "V4-S7": "BLOCKED on explicit user approval", "V4-S8..S12": "NOT STARTED (provider phases)",
        },
        "state": {"status": state.get("status"), "work_queue_version": state.get("work_queue_version"),
                  "next_task": state.get("next_task")},
        "evidence": [reference(GATES / "V4_S5_RELEASE_FREEZE_001.json"),
                     reference(GATES / "V4_S6_RUN_MANIFEST_FREEZE_001.json"),
                     reference(ART / "provider-approval-request-001.json")],
    }
    write_new(ART / "phase-abc-closure-001.json", record)
    print(json.dumps({"release_id": record["release_id"],
                      "candidate_tree": record["candidate_source_tree_sha256"][:16],
                      "next": record["state"]["next_task"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
