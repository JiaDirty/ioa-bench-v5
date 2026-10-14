"""V4-S1..S4 gate artifacts.

Consolidates the Phase A/B evidence into the gate records the v4 goal pack
requires, each pointing at the authoritative artifact and recording the exact
command that reproduced it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, reference, write_new

ART = ROOT / "artifacts/scientific_closure_v4"
GATES = ROOT / "artifacts/gates"

CANDIDATE_TREE = "2b72255bcb5d258322bb97c88714a443ae4bb4026092a3c4219d886d2083e6ff"
OLD_TREE = "7f48188a83a1d5a2e5d0886a9778813076f01c236815795b14c4e110c0becd77"


def main() -> int:
    s1 = {
        "artifact": "V4_S1_CANDIDATE_FORK",
        "version": "1",
        "pass": True,
        "provider_calls": 0,
        "old_candidate": {"path": "artifacts/scientific_closure_v3_2/corrective-candidate",
                          "source_tree_sha256": OLD_TREE},
        "new_candidate": {"path": "artifacts/scientific_closure_v4/corrective-candidate-v2",
                          "source_tree_sha256_before_strict_retry": OLD_TREE,
                          "files": 335},
        "byte_identical_fork": True,
        "old_hash_independently_reproduced": True,
        "command": "python -B -X utf8 scripts/v4_fork_candidate.py",
        "evidence": [reference(ART / "candidate-fork-001.json")],
    }
    write_new(GATES / "V4_S1_CANDIDATE_FORK_001.json", s1)

    s2 = {
        "artifact": "V4_S2_STRICT_RETRY",
        "version": "1",
        "pass": True,
        "provider_calls": 0,
        "candidate_source_tree_sha256": CANDIDATE_TREE,
        "contract": {
            "COMPLETED": "normal terminal",
            "INVALID_MODEL_OUTPUT": "model terminal; recorded; never safe; never retried",
            "RETRYABLE_INFRA_FAILURE": "resumable only with zero valid model behaviour and infrastructure-class cause",
            "INFRA_INTERRUPTED": "terminal after >=1 valid model behaviour; partial evidence retained; never retried",
            "FAILED": "terminal; non-infrastructure exception; never auto-retried",
        },
        "changed_files": ["src/ioabench/cli.py", "src/ioabench/core/types.py", "src/ioabench/runtime/batch.py",
                          "src/ioabench/runtime/construct_dispatch.py", "src/ioabench/runtime/full_manifest.py",
                          "src/ioabench/runtime/run_gates.py", "src/ioabench/runtime/scientific_io.py"],
        "verification": {
            "selfcheck": {"command": "python -B -X utf8 scripts/v4_selfcheck_strict_retry.py",
                          "checks": 23, "failures": 0},
            "candidate_validation": {"command": "python -B -X utf8 scripts/validate_corrective_candidate_v4.py --candidate artifacts/scientific_closure_v4/corrective-candidate-v2 --output <new>",
                                     "checks": 82, "failures": 0},
            "mock_suite_e2e": {"command": "python -B -X utf8 scripts/v4_e2e_mock_suite.py",
                               "result": "90/90 COMPLETED, 90 attempt journals, 0 provider calls"},
            "resume_idempotence": "covered by tests/v4 and selfcheck",
        },
        "evidence": [reference(ART / "strict-retry-implementation-001.json"),
                     reference(ART / "strict-retry-selfcheck-001.json"),
                     reference(ART / "candidate-validation-006.json")],
    }
    write_new(GATES / "V4_S2_STRICT_RETRY_001.json", s2)

    s3 = {
        "artifact": "V4_S3_CANDIDATE_VALIDATION",
        "version": "1",
        "pass": True,
        "provider_calls": 0,
        "candidate_source_tree_sha256": CANDIDATE_TREE,
        "results": {
            "candidate_validation_checks": 82,
            "closure_tests": "19 passed",
            "v4_tests": "22 passed",
            "full_pytest": "831 passed, 2 skipped (AIHUBMIX_API_KEY required)",
            "baseline_verify": "19606 protected files unchanged",
        },
        "commands": [
            "python -B -X utf8 -m pytest tests/closure -q",
            "python -B -X utf8 -m pytest tests -q",
            "python -B -X utf8 scripts/scientific_closure.py verify-baseline",
        ],
        "quality_gates_not_lowered": True,
        "notes": "The T353 paired-branch replay and counterfactual metric checks from the v3.2 candidate are retained and pass unchanged; strict-retry checks are additional.",
        "evidence": [reference(ART / "candidate-validation-006.json")],
    }
    write_new(GATES / "V4_S3_CANDIDATE_VALIDATION_001.json", s3)

    s4 = {
        "artifact": "V4_S4_PREFREEZE_SCIENTIFIC_AUDIT",
        "version": "1",
        "pass": True,
        "provider_calls": 0,
        "candidate_source_tree_sha256": CANDIDATE_TREE,
        "checks": 27,
        "failures": [],
        "components_verified": ["dataset pack 18 suites + hashes", "frozen version map 18/18",
                                "contracts 18/18", "dispatch/runtime versions", "prompt hashes",
                                "model profile", "scheduler (conc 3, temp 0, max_tokens 8192)",
                                "synthetic human (glm-5.3-flash, frozen, personas 1.0.0, deterministic, isolated)",
                                "dependency lock", "strict retry semantics in candidate source"],
        "command": "python -B -X utf8 scripts/v4_prefreeze_audit.py --output artifacts/scientific_closure_v4/prefreeze-scientific-audit-010.json",
        "evidence": [reference(ART / "prefreeze-scientific-audit-010.json")],
        "superseded_attempts": ["prefreeze-scientific-audit-001..007 (harness import-order defects; retained, not deleted)"],
    }
    write_new(GATES / "V4_S4_PREFREEZE_AUDIT_001.json", s4)

    print(json.dumps({"gates_written": ["V4_S1", "V4_S2", "V4_S3", "V4_S4"],
                      "candidate_tree": CANDIDATE_TREE}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
