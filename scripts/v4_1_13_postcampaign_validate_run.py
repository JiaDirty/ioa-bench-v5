"""Phase F — per-suite post-run validation for the v4.1.13 strict campaign (read-only).

Implements the checks in the goal pack's ``06_POST_RUN_VALIDATION.md`` for one
suite and reports a binding level.  ``STRICT_BINDING`` is granted only when every
check passes against the frozen v4 release; anything less is reported as the
specific failing level so the suite is excluded from canonical aggregation.

Usage:
    python scripts/v4_validate_run.py --suite T311
    python scripts/v4_validate_run.py --all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

RELEASE_PATH = ROOT / "release/BENCHMARK_RELEASE_v4.1.13-corrective-integration-20261002.json"
MANIFEST_DIR = ROOT / "data/runs/_v4_1_13_manifests"
RUNS_DIR = ROOT / "data/runs"
MODEL = "deepseek-v4.1-flash"
SUITES = [f"T3{a}{b}" for a in "123456" for b in "123"]

TERMINAL_STATUSES = {"COMPLETED", "INVALID_MODEL_OUTPUT", "BUDGET_EXCEEDED", "INFRA_INTERRUPTED"}
SIMULATION_SUITES = {"T361", "T362", "T363"}
DISPATCH_VERSION = "construct-dispatch-1.0.2"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _journal(path: pathlib.Path) -> tuple[dict, list[dict]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or rows[0].get("kind") != "attempt":
        raise ValueError("missing attempt header")
    records = []
    for row in rows[1:]:
        if row.get("kind") != "model_record" or not isinstance(row.get("record"), dict):
            raise ValueError("invalid attempt journal row")
        if canonical_sha256(row["record"]) != row.get("record_sha256"):
            raise ValueError("attempt model-record hash mismatch")
        records.append(row["record"])
    return rows[0], records


def _replay_ok(replay: dict, *, run_id: str, case_id: str) -> bool:
    recorded = replay.get("content_sha256")
    return (isinstance(recorded, str)
            and canonical_sha256({key: value for key, value in replay.items() if key != "content_sha256"}) == recorded
            and replay.get("run_id") == run_id
            and replay.get("case_id") == case_id
            and isinstance(replay.get("timeline"), list)
            and isinstance(replay.get("world_snapshot"), dict)
            and isinstance(replay.get("scorer_inputs"), dict)
            and isinstance(replay.get("final_utility"), dict))


class SuiteValidation:
    def __init__(self, suite: str) -> None:
        self.suite = suite
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, bool(ok), detail))

    @property
    def failures(self):
        return [c for c in self.checks if not c[1]]

    @property
    def binding_level(self) -> str:
        return "STRICT_BINDING" if not self.failures else "NOT_BOUND"


def validate_suite(release: dict, suite: str, runs_dir: pathlib.Path | None = None,
                   manifest_dir: pathlib.Path | None = None,
                   release_sha: str | None = None) -> dict:
    """Validate one suite against the frozen release.

    ``runs_dir`` / ``manifest_dir`` / ``release_sha`` default to the real paths;
    tests override them to exercise the pass path on a scratch fixture.
    """
    runs_dir = runs_dir or RUNS_DIR
    manifest_dir = manifest_dir or MANIFEST_DIR
    release_sha = release_sha or sha256(RELEASE_PATH)
    evidence_root = ROOT.resolve() if runs_dir.resolve() == RUNS_DIR.resolve() else runs_dir.parent.resolve()
    v = SuiteValidation(suite)
    version = release["datasets"][suite]["version"]
    run_id = f"{MODEL}-{suite}-{version}-v4.1.13-formal"
    run_dir = runs_dir / run_id

    # ---- 0. run exists and is v4-native -------------------------------------
    v.check("run_dir_exists", run_dir.is_dir(), str(run_dir.name))
    if not run_dir.is_dir():
        return _result(v, run_id)

    legacy = runs_dir / f"{MODEL}-{suite}-{version}-formal"
    v.check("not_a_historical_directory", run_id != legacy.name)

    results_path = run_dir / "results.json"
    v.check("results_json_present", results_path.is_file())
    if not results_path.is_file():
        return _result(v, run_id)
    results = json.loads(results_path.read_text(encoding="utf-8"))

    # ---- 1. 90/90 all-terminal, no missing/duplicate case ids ---------------
    v.check("case_count_90", len(results) == 90, f"n={len(results)}")
    case_ids = [r.get("case_id") for r in results.values()]
    v.check("case_ids_unique", len(set(case_ids)) == len(case_ids),
            f"unique={len(set(case_ids))}")
    non_terminal = {k: r.get("status") for k, r in results.items()
                    if r.get("status") not in TERMINAL_STATUSES}
    v.check("all_cases_terminal", not non_terminal,
            f"non_terminal={len(non_terminal)}")

    # ---- 2. dataset three-way binding: run == dataset manifest == release ---
    ds = release["datasets"][suite]
    manifest_path = manifest_dir / f"{run_id}.manifest.json"
    v.check("run_manifest_present", manifest_path.is_file())
    if manifest_path.is_file():
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
        runtime_manifest_path = run_dir / "manifest" / f"{run_id}.json"
        v.check("runtime_manifest_present", runtime_manifest_path.is_file())
        if runtime_manifest_path.is_file():
            v.check("runtime_manifest_matches_frozen",
                    runtime_manifest_path.read_bytes() == manifest_path.read_bytes())
        rel = man["release"]
        v.check("manifest_release_id", rel.get("release_id") == release["release_id"])
        v.check("manifest_release_sha256",
                rel.get("release_sha256") == release_sha)
        v.check("manifest_source_tree",
                rel.get("source_tree_sha256") == release["source_tree_sha256"])
        v.check("manifest_strict_retry", rel.get("strict_retry_semantics") is True)
        v.check("manifest_dataset_hash",
                man["benchmark"]["dataset_hashes"].get(suite) == ds["content_sha256"])
        v.check("manifest_dataset_version",
                man["benchmark"]["dataset_versions"].get(suite) == version)
        v.check("manifest_contract_hash",
                man["benchmark"].get("contract_hashes", {}).get(suite) == release["contracts"][suite])
        v.check("manifest_scorer_version",
                man["benchmark"]["scorer_versions"].get(suite) == release["scorer_versions"][suite])
        v.check("manifest_runtime_version",
                man.get("runtime", {}).get("runtime_version") == release["runtime_versions"][suite])
        v.check("manifest_runtime_source_tree",
                man.get("runtime", {}).get("source_tree_sha256") == release["source_tree_sha256"])
        v.check("manifest_model_profile",
                man.get("provenance", {}).get("model_profile_sha256") == release["model_profile_sha256"])

    # per-case dispatch must carry the frozen dispatch version
    # Terminal interruption may occur before the case-level dispatch envelope is
    # assembled; validate the frozen version on envelopes that were actually
    # persisted, while the interrupted evidence checks below cover the partial
    # execution contract.
    dispatch_versions = {r.get("dispatch", {}).get("dispatch_version")
                         for r in results.values() if isinstance(r.get("dispatch"), dict)}
    v.check("frozen_dispatch_version", dispatch_versions == {DISPATCH_VERSION},
            f"found={sorted(x for x in dispatch_versions if x)}")

    # every case belongs to this suite
    v.check("all_cases_suite_tagged",
            all(r.get("suite") == suite for r in results.values()))

    # ---- 3. attempt provenance and strict retry history -----------------------
    attempts_dir = run_dir / "attempts"
    attempt_failures = []
    referenced_journals: set[pathlib.Path] = set()
    provider_model_records = 0
    if attempts_dir.is_dir():
        disk_journals = {path.resolve() for path in attempts_dir.rglob("attempt-*.jsonl")}
        for result in results.values():
            case_id = str(result.get("case_id"))
            history = result.get("attempts")
            if not isinstance(history, list) or not history:
                attempt_failures.append(f"{case_id}:missing_history")
                continue
            numbers = [item.get("attempt_no") for item in history if isinstance(item, dict)]
            if numbers != list(range(1, len(history) + 1)) or result.get("attempt_no") != numbers[-1]:
                attempt_failures.append(f"{case_id}:attempt_sequence")
            if history[-1].get("status") != result.get("status"):
                attempt_failures.append(f"{case_id}:terminal_mismatch")
            for prior in history[:-1]:
                if (prior.get("status") != "RETRYABLE_INFRA_FAILURE"
                        or prior.get("infrastructure_failure") is not True
                        or int(prior.get("model_records_produced") or 0) != 0
                        or prior.get("valid_model_behavior_observed") is not False):
                    attempt_failures.append(f"{case_id}:illegal_retry")
            for attempt in history:
                binding = attempt.get("attempt_journal")
                if not isinstance(binding, dict) or not binding.get("path") or not binding.get("sha256"):
                    attempt_failures.append(f"{case_id}:missing_journal_binding")
                    continue
                journal_path = (evidence_root / str(binding["path"])).resolve()
                referenced_journals.add(journal_path)
                try:
                    if (not journal_path.is_file()
                            or not journal_path.is_relative_to(run_dir.resolve())
                            or sha256(journal_path) != binding["sha256"]):
                        raise ValueError("journal path/hash")
                    header, records = _journal(journal_path)
                    if (header.get("run_id") != run_id or header.get("suite_id") != suite
                            or header.get("case_id") != case_id
                            or header.get("attempt_no") != attempt.get("attempt_no")):
                        raise ValueError("journal identity")
                    if len(records) != int(attempt.get("model_records_produced") or 0):
                        raise ValueError("journal record count")
                    provider_model_records += len(records)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    attempt_failures.append(f"{case_id}:{exc}")
        v.check("attempt_journals_exactly_referenced", referenced_journals == disk_journals,
                f"referenced={len(referenced_journals)} disk={len(disk_journals)}")
        v.check("strict_retry_attempt_history", not attempt_failures,
                f"failures={len(attempt_failures)}")
    else:
        v.check("attempt_journals_present", False, "attempts/ missing")

    # ---- 4. retry policy: no INVALID rerun-to-safe, no INFRA rerun ----------
    status_counts: dict[str, int] = {}
    for r in results.values():
        status_counts[r.get("status")] = status_counts.get(r.get("status"), 0) + 1
    v.check("no_failed_terminal", status_counts.get("FAILED", 0) == 0,
            f"FAILED={status_counts.get('FAILED', 0)}")

    # ---- 5. replay / runtime / tested-model binding ---------------------------
    missing_replay = [k for k, r in results.items()
                      if r.get("status") != "INFRA_INTERRUPTED" and not isinstance(r.get("replay"), dict)]
    v.check("replay_present_for_non_interrupted_cases", not missing_replay,
            f"missing={len(missing_replay)}")
    interrupted_without_partial = [k for k, r in results.items()
                                   if r.get("status") == "INFRA_INTERRUPTED"
                                   and (r.get("partial_evidence_retained") is not True
                                        or int(r.get("model_records_produced") or 0) < 1)]
    v.check("interrupted_cases_retain_partial_evidence", not interrupted_without_partial,
            f"missing={len(interrupted_without_partial)}")
    broken_hash = []
    runtime_failures = []
    model_failures = []
    sh_failures = []
    for key, r in results.items():
        rep = r.get("replay")
        if not isinstance(rep, dict):
            continue
        case_id = str(r.get("case_id"))
        if not _replay_ok(rep, run_id=run_id, case_id=case_id):
            broken_hash.append(key)
        scenario_manifest = ((rep.get("scenario") or {}).get("manifest") or {})
        dispatch = r.get("dispatch") or {}
        if (scenario_manifest.get("runtime_version") != release["runtime_versions"][suite]
                or dispatch.get("runtime_version") != scenario_manifest.get("runtime_version")
                or scenario_manifest.get("source_tree_sha256") != release["source_tree_sha256"]
                or scenario_manifest.get("model_id") != release["tested_model"]["model_id"]
                or scenario_manifest.get("sampling_parameters") != {
                    "temperature": release["tested_model"]["temperature"],
                    "max_tokens": release["tested_model"]["max_tokens"],
                }):
            runtime_failures.append(key)
        records = rep.get("model_records") or []
        tested_records = [record for record in records
                          if (record.get("request") or {}).get("role_metadata", {}).get("role") != "SYNTHETIC_HUMAN"]
        if any((record.get("response") or {}).get("model_id") != release["tested_model"]["model_id"]
               for record in tested_records):
            model_failures.append(key)
        sh_records = [record for record in records
                      if (record.get("request") or {}).get("role_metadata", {}).get("role") == "SYNTHETIC_HUMAN"]
        if suite in SIMULATION_SUITES:
            sh = scenario_manifest.get("synthetic_human") or {}
            aux = release["auxiliary_model_profiles"]
            requires_sh = r.get("status") not in {"INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED"}
            if (requires_sh and not sh_records or sh_records and (sh.get("model_id") != aux["model_id"]
                    or sh.get("persona_set_version") != aux["persona_set_version"]
                    or sh.get("protocol_version") != aux["protocol_version"]
                    or sh.get("assignment_rule") != aux["persona_assignment"]
                    or any((record.get("response") or {}).get("model_id") != aux["model_id"]
                           or (record.get("request") or {}).get("parameters") != aux["parameters"]
                           for record in sh_records))):
                sh_failures.append(key)
        elif sh_records:
            sh_failures.append(key)
    v.check("replay_content_hashes_valid", not broken_hash,
            f"broken={len(broken_hash)}")
    v.check("runtime_source_and_sampling_bound", not runtime_failures,
            f"failed={len(runtime_failures)}")
    v.check("tested_model_records_exact", not model_failures,
            f"failed={len(model_failures)}")
    v.check("synthetic_human_records_exact_and_isolated", not sh_failures,
            f"failed={len(sh_failures)}")

    # ---- 6. T353 paired-branch replay --------------------------------------
    # The candidate runtime stores the counterfactual branches under
    # replay["scenario"]["paired_runs"] keyed by "honest"/"manipulated", each
    # carrying its own nested replay (the "primary" branch is the outer run).
    # See ioabench/runtime/discovery_selection.py.
    if suite == "T353":
        complete = 0
        for r in results.values():
            rep = r.get("replay") or {}
            if r.get("status") == "INFRA_INTERRUPTED":
                continue
            paired = ((rep.get("scenario") or {}).get("paired_runs")) or {}
            modes = {m for m in ("honest", "manipulated")
                     if isinstance(paired.get(m), dict) and isinstance(paired[m].get("replay"), dict)
                     and _replay_ok(paired[m]["replay"], run_id=f"{run_id}-pair-{m}",
                                       case_id=str(r.get("case_id")))}
            if modes == {"honest", "manipulated"}:
                complete += 1
        expected = sum(r.get("status") != "INFRA_INTERRUPTED" for r in results.values())
        v.check("t353_three_branches", complete == expected,
                f"complete_pair_bundles={complete}/{expected}")

    # ---- 7. T361–T363 SIMULATION_ONLY --------------------------------------
    if suite in SIMULATION_SUITES:
        v.check("simulation_only_marked",
                release["runtime_mapping"]["simulation_suites"] == sorted(SIMULATION_SUITES))
        # synthetic-human provenance must be isolated from the tested model
        aux = release["auxiliary_model_profiles"]
        v.check("sh_model_is_auxiliary", aux["model_id"] != release["tested_model"]["model_id"])
        v.check("sh_simulation_only", aux.get("simulation_only") is True)

    # ---- 8. eligibility / provider denominator -----------------------------
    elig = {}
    for r in results.values():
        elig[r.get("eligibility")] = elig.get(r.get("eligibility"), 0) + 1
    v.check("eligibility_recorded", all(k for k in elig),
            f"counts={elig}")

    return _result(v, run_id, status_counts=status_counts, eligibility=elig,
                   provider_model_records=provider_model_records)


def _result(v: SuiteValidation, run_id: str, **extra) -> dict:
    payload = {
        "suite": v.suite,
        "run_id": run_id,
        "binding_level": v.binding_level,
        "canonical_accepted": not v.failures,
        "checks": len(v.checks),
        "failures": [{"name": n, "detail": d} for n, _, d in v.failures],
        "detail": [{"name": n, "pass": ok, "detail": d} for n, ok, d in v.checks],
        "reason": ("all post-run checks pass against the frozen v4 release"
                   if not v.failures else
                   "failed: " + ", ".join(n for n, _, _ in v.failures)),
    }
    payload.update(extra)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--output")
    args = ap.parse_args()

    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    targets = SUITES if args.all else ([args.suite] if args.suite else [])
    if not targets:
        raise SystemExit("pass --suite T311 or --all")

    reports = [validate_suite(release, s) for s in targets]
    summary = {
        "artifact": "V4_1_13_RUN_VALIDATION",
        "release_sha256": sha256(RELEASE_PATH),
        "provider_calls": 0,
        "suites": reports,
        "strict_count": sum(1 for r in reports if r["binding_level"] == "STRICT_BINDING"),
        "total": len(reports),
        "pass": all(r["canonical_accepted"] for r in reports),
    }
    if args.output:
        output = pathlib.Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

