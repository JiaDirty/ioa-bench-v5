"""DW-AUDIT-009 acceptance: the 18-suite evidence matrix is backed by real runs of both runner
entries, monitor reports are present and green, and every suite records scorer/novelty/gap rows."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "artifacts/v5/dynamic_world/suite-evidence-matrix.json"

EXPECTED_SUITES = {f"T3{a}{b}" for a in range(1, 7) for b in range(1, 4)}


def _matrix() -> dict:
    if not MATRIX.exists():
        pytest.skip("suite-evidence-matrix.json has not been generated yet")
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def test_matrix_covers_all_18_suites() -> None:
    matrix = _matrix()
    assert set(matrix["suites"]) == EXPECTED_SUITES
    assert matrix["totals"]["suites"] == 18


@pytest.mark.parametrize("sid", sorted(EXPECTED_SUITES))
def test_each_suite_has_real_runs_of_both_runners(sid: str) -> None:
    matrix = _matrix()
    row = matrix["suites"][sid]
    assert row["classic_runner"]["run"]["status"] == "COMPLETED", row["classic_runner"]
    assert row["classic_runner"]["entry"].startswith("runner.run_case")
    assert row["dynamic_runner"]["run"]["status"] == "COMPLETED", row["dynamic_runner"]
    assert row["dynamic_runner"]["entry"].startswith("dynamic.runner.run_dynamic_case")
    assert row["dynamic_runner"]["run"].get("scientifically_eligible") is True


@pytest.mark.parametrize("sid", sorted(EXPECTED_SUITES))
def test_each_suite_records_monitor_scorer_novelty_gap(sid: str) -> None:
    matrix = _matrix()
    row = matrix["suites"][sid]
    # monitor support is backed by the dynamic run's mandatory monitor report
    assert row["monitor_support"]["mandatory_per_episode"] is True
    assert row["monitor_support"]["ledger_integrity"] == "one_to_one_action_seq"
    assert row["dynamic_runner"]["monitor_report"]["ledger_integrity"]["passed"] is True
    # scorer identity + audit status
    assert row["scorer"]["classic_scorer_version"]
    assert row["scorer"]["audit_status"]
    # novelty evidence: the slice structure differs from the classic template on real dimensions
    assert row["novelty_evidence"]["slice_vs_classic_dimensions"], \
        f"{sid}: slice must be structurally distinct from the classic template"
    assert row["novelty_evidence"]["family_registry"]["status"] in ("entries_present", "NO_REFERENCE")
    # residual capability gap is explicit
    assert row["capability_gap"]


def test_matrix_totals_match_run_results() -> None:
    matrix = _matrix()
    totals = matrix["totals"]
    assert totals["classic_runs_completed"] == 18
    assert totals["dynamic_runs_completed"] == 18
    assert totals["dynamic_runs_eligible"] == 18


def test_simulation_suites_are_marked() -> None:
    matrix = _matrix()
    for sid in ("T361", "T362", "T363"):
        assert matrix["suites"][sid]["simulation_only"] is True
        assert matrix["suites"][sid]["cluster"] == "simulation-only"


def test_honest_limit_statement_present() -> None:
    matrix = _matrix()
    assert "do not equal a mature AI auto-generation system" in matrix["honest_limit"]


@pytest.mark.parametrize("sid", sorted(EXPECTED_SUITES))
def test_stage_c_field_set_recorded_per_suite(sid: str) -> None:
    """04 contract stage C: each suite provides adapter_id, can_compile_blueprints,
    replay_coverage, monitor_support, scorer_audit, human_review_status — with gated items
    recorded honestly rather than claimed."""
    matrix = _matrix()
    fields = matrix["suites"][sid]["stage_c_fields"]
    assert fields["adapter_id"].startswith(f"{sid.lower()}_slice:")
    assert fields["can_compile_blueprints"].startswith("NOT_STARTED")
    assert "replay" in fields["replay_coverage"].lower()
    assert "mandatory per episode" in fields["monitor_support"]
    assert fields["scorer_audit"]
    assert fields["human_review_status"] == ("BLOCKED_EXTERNAL_REVIEW — Gate D requires real "
                                             "independent human experts (not yet available)")
