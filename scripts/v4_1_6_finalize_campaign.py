"""Build the v4.1.6 canonical report and delivery bundle after Phase G.

This is a post-run, read-only consumer. It never calls a Provider and refuses
to produce canonical output unless every suite is STRICT_BINDING.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import zlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SUITES = tuple(f"T3{a}{b}" for a in "123456" for b in "123")
SIMULATION_ONLY = {"T361", "T362", "T363"}
FAMILIES = {
    "trust_and_authorization": ("T311", "T312", "T313"),
    "protocol_interoperability": ("T321", "T322", "T323"),
    "propagation_and_inferability": ("T331", "T332", "T333"),
    "public_knowledge_integrity": ("T341", "T342", "T343"),
    "ecosystem_power_balance": ("T351", "T352", "T353"),
    "human_agency_erosion_SIMULATION_ONLY": ("T361", "T362", "T363"),
}
TERMINAL = {"COMPLETED", "INVALID_MODEL_OUTPUT", "INFRA_INTERRUPTED"}
SECRET_BYTES = (
    re.compile(rb"AIHUBMIX_API_KEY\s*=\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(rb"Bearer\s+[A-Za-z0-9_\-]{20,}"),
    re.compile(rb"sk-[A-Za-z0-9]{16,}"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def ref(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256_bytes(payload.encode("utf-8"))


def load_release() -> tuple[dict, Path, str]:
    path = ROOT / "release/BENCHMARK_RELEASE_v4.1.6-corrective-integration-20261002.json"
    return read_json(path), path, sha256(path)


def assert_audit(audit: dict, release: dict, release_sha: str) -> None:
    if (audit.get("release_id") != release["release_id"]
            or audit.get("release_sha256") != release_sha
            or audit.get("source_tree_sha256") != release["source_tree_sha256"]):
        raise ValueError("binding audit is not bound to the current v4.1.6 Release")
    if audit.get("pass") is not True or audit.get("verdict") != "STRICT_18_OF_18":
        raise ValueError("canonical aggregation requires STRICT_18_OF_18")
    if audit.get("historical_runs_consumed") != 0:
        raise ValueError("historical runs cannot enter v4 canonical aggregation")
    rows = audit.get("suites", [])
    if len(rows) != 18 or {r.get("suite") for r in rows} != set(SUITES):
        raise ValueError("binding audit must contain each suite exactly once")
    if any(r.get("binding_level") != "STRICT_BINDING" or r.get("canonical_accepted") is not True for r in rows):
        raise ValueError("every canonical suite must be STRICT_BINDING and accepted")


def validate_suite(row: dict, release: dict, release_sha: str) -> tuple[dict, dict]:
    suite = row["suite"]
    run_id = row["run_id"]
    run_dir = ROOT / "data/runs" / run_id
    result_path = run_dir / "results.json"
    runtime_manifest_path = run_dir / "manifest" / f"{run_id}.json"
    frozen_manifest_path = ROOT / "data/runs/_v4_1_6_manifests" / f"{run_id}.manifest.json"
    if not result_path.is_file() or not runtime_manifest_path.is_file() or not frozen_manifest_path.is_file():
        raise ValueError(f"missing formal evidence for {suite}")
    results = read_json(result_path)
    runtime_manifest = read_json(runtime_manifest_path)
    frozen_manifest = read_json(frozen_manifest_path)
    if runtime_manifest_path.read_bytes() != frozen_manifest_path.read_bytes():
        raise ValueError(f"runtime Manifest differs from frozen Manifest for {suite}")
    binding = runtime_manifest.get("release", {})
    if (binding.get("release_id") != release["release_id"]
            or binding.get("release_sha256") != release_sha
            or binding.get("source_tree_sha256") != release["source_tree_sha256"]):
        raise ValueError(f"runtime Manifest Release binding failed for {suite}")
    version = release["datasets"][suite]["version"]
    dataset_dir = ROOT / "data/datasets" / suite / version
    dataset_manifest_path = dataset_dir / "manifest.json"
    cases_path = dataset_dir / "cases.jsonl"
    dataset_manifest = read_json(dataset_manifest_path)
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    actual_dataset_hash = canonical_hash({"manifest": {**dataset_manifest, "content_sha256": None}, "cases": cases})
    if (sha256(dataset_manifest_path) != release["datasets"][suite]["manifest_sha256"]
            or actual_dataset_hash != release["datasets"][suite]["content_sha256"]
            or dataset_manifest.get("content_sha256") != actual_dataset_hash):
        raise ValueError(f"dataset hash binding failed for {suite}")
    expected_ids = {case["candidate_id"] for case in cases}
    result_ids = [value.get("case_id") for value in results.values()]
    if len(results) != 90 or len(set(result_ids)) != 90 or set(result_ids) != expected_ids:
        raise ValueError(f"case coverage failed for {suite}")
    if any(value.get("suite") != suite for value in results.values()):
        raise ValueError(f"suite tags failed for {suite}")
    if any(value.get("status") not in TERMINAL for value in results.values()):
        raise ValueError(f"non-terminal result in {suite}")
    if any(value.get("status") == "RETRYABLE_INFRA_FAILURE" for value in results.values()):
        raise ValueError(f"retryable result remains in {suite}")
    attempts = list((run_dir / "attempts").rglob("attempt-*.jsonl"))
    if len(attempts) < 90:
        raise ValueError(f"attempt journals are incomplete for {suite}")
    for value in results.values():
        history = value.get("attempts")
        if not isinstance(history, list) or not history:
            raise ValueError(f"attempt provenance missing for {suite}")
        numbers = [attempt.get("attempt_no") for attempt in history]
        if numbers != list(range(1, len(history) + 1)) or value.get("attempt_no") != numbers[-1]:
            raise ValueError(f"attempt numbering failed for {suite}")
        if history[-1].get("status") != value.get("status"):
            raise ValueError(f"terminal attempt mismatch for {suite}")
        for attempt in history[:-1]:
            if (attempt.get("status") != "RETRYABLE_INFRA_FAILURE"
                    or attempt.get("infrastructure_failure") is not True
                    or int(attempt.get("model_records_produced") or 0) != 0
                    or attempt.get("valid_model_behavior_observed") is not False):
                raise ValueError(f"illegal retry provenance for {suite}")
        for attempt in history:
            journal = attempt.get("attempt_journal")
            if not isinstance(journal, dict) or not journal.get("path") or not journal.get("sha256"):
                raise ValueError(f"attempt journal binding missing for {suite}")
            journal_path = ROOT / journal["path"]
            if (not journal_path.is_file() or not journal_path.resolve().is_relative_to(run_dir.resolve())
                    or sha256(journal_path) != journal["sha256"]):
                raise ValueError(f"attempt journal hash failed for {suite}")
        replay = value.get("replay")
        if value.get("status") == "INFRA_INTERRUPTED":
            if (value.get("partial_evidence_retained") is not True
                    or int(value.get("model_records_produced") or 0) < 1):
                raise ValueError(f"interrupted evidence missing for {suite}")
            continue
        if not isinstance(replay, dict):
            raise ValueError(f"replay missing for {suite}")
        recorded = replay.get("content_sha256")
        if not recorded or canonical_hash({key: item for key, item in replay.items() if key != "content_sha256"}) != recorded:
            raise ValueError(f"replay hash failed for {suite}")
        if suite == "T353":
            paired = (replay.get("scenario") or {}).get("paired_runs") or {}
            if any(not isinstance(paired.get(mode), dict) or not isinstance(paired[mode].get("replay"), dict)
                   for mode in ("honest", "manipulated")):
                raise ValueError("T353 paired replay is incomplete")
    if suite in SIMULATION_ONLY and runtime_manifest.get("runtime", {}).get("simulation_only") is not True:
        raise ValueError(f"SIMULATION_ONLY binding missing for {suite}")
    return {"run_id": run_id, "run_dir": run_dir, "results": results, "manifest": runtime_manifest}, {
        "dataset_dir": dataset_dir, "dataset_manifest": dataset_manifest, "cases": cases,
        "evidence": [ref(result_path), ref(runtime_manifest_path), ref(dataset_manifest_path), ref(cases_path)],
    }


def summarize(suite: str, run: dict) -> dict:
    outcomes: dict[str, int] = {}
    utility = invalid = interrupted = tokens = recorded_model_responses = 0
    by_difficulty: dict[str, dict] = {}
    for value in run["results"].values():
        score = value.get("score") or {}
        outcome = score.get("outcome_class") or value.get("status") or "UNKNOWN"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        difficulty = str(value.get("difficulty", "unknown"))
        bucket = by_difficulty.setdefault(difficulty, {"cases": 0, "outcomes": {}, "utility_true": 0})
        bucket["cases"] += 1
        bucket["outcomes"][outcome] = bucket["outcomes"].get(outcome, 0) + 1
        if score.get("task_utility") is True:
            utility += 1
            bucket["utility_true"] += 1
        if value.get("status") == "INVALID_MODEL_OUTPUT":
            invalid += 1
        if value.get("status") == "INFRA_INTERRUPTED":
            interrupted += 1
        recorded_model_responses += sum(int(attempt.get("model_records_produced") or 0)
                                        for attempt in value.get("attempts", []))
        for record in (value.get("replay") or {}).get("model_records", []):
            tokens += int(((record.get("response") or {}).get("usage") or {}).get("total_tokens") or 0)
    result = {"suite": suite, "cases": len(run["results"]), "outcomes": outcomes, "utility_true": utility,
              "task_utility_rate": round(utility / len(run["results"]), 4),
              "invalid_model_output_cases": invalid, "infra_interrupted_cases": interrupted,
              "recorded_model_responses": recorded_model_responses,
              "total_output_tokens": tokens, "by_difficulty": by_difficulty}
    if suite in SIMULATION_ONLY:
        result["SIMULATION_ONLY"] = True
    return result


def html_dashboard(campaign: dict) -> str:
    rows = []
    for suite, value in campaign["suite_results"].items():
        rows.append("<tr><th>%s%s</th><td>%d</td><td>%s</td><td>%.4f</td><td>%d / %d</td></tr>" % (
            html.escape(suite), " (SIMULATION_ONLY)" if value.get("SIMULATION_ONLY") else "", value["cases"],
            html.escape(json.dumps(value["outcomes"], ensure_ascii=False, sort_keys=True)), value["task_utility_rate"],
            value["invalid_model_output_cases"], value["infra_interrupted_cases"]))
    run_ids = "".join(f"<li><code>{html.escape(suite)}</code>: <code>{html.escape(run_id)}</code></li>" for suite, run_id in campaign["canonical_run_ids"].items())
    return f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>IoA-Bench v4.1.6</title><style>body{{font:16px Segoe UI,Microsoft YaHei,sans-serif;max-width:1100px;margin:auto;padding:24px;color:#17212b}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #cbd5e1;text-align:left;overflow-wrap:anywhere}}.status{{padding:14px;background:#ecfdf5}}code{{overflow-wrap:anywhere}}</style><h1>IoA-Bench v4.1.6 canonical report</h1><p class='status'>STRICT_18_OF_18 · 1620 cases · safety and utility are separate</p><p>Release <code>{campaign['release']['release_id']}</code>; source tree <code>{campaign['release']['source_tree_sha256']}</code>.</p><table><tr><th>Suite</th><th>Cases</th><th>Outcomes</th><th>Utility</th><th>Invalid / Interrupted</th></tr>{''.join(rows)}</table><h2>Canonical Run IDs</h2><ul>{run_ids}</ul><p>T361-T363 are SIMULATION_ONLY. T353 includes primary, honest and manipulated replay branches. Historical v3/v3.2 runs are excluded.</p></html>"


def markdown_report(campaign: dict) -> str:
    lines = ["# IoA-Bench v4.1.6 canonical report", "", "Verdict: **STRICT_18_OF_18**.",
             "", "The tested model is `deepseek-v4.1-flash`. Safety outcomes and task utility are reported separately; no overall safety score is produced.",
             "", "T361-T363 are `SIMULATION_ONLY` using the frozen synthetic-human profile.", "", "| Suite | Cases | Outcomes | Utility |", "|---|---:|---|---:|"]
    for suite, value in campaign["suite_results"].items():
        lines.append(f"| {suite} | {value['cases']} | `{json.dumps(value['outcomes'], sort_keys=True)}` | {value['task_utility_rate']:.4f} |")
    lines.extend(["", "## Denominators", "",
                  f"- Recorded model responses: `{campaign['recorded_model_responses']}`.",
                  f"- `INVALID_MODEL_OUTPUT` cases: `{campaign['invalid_model_output_cases']}`.",
                  f"- `INFRA_INTERRUPTED` cases: `{campaign['infra_interrupted_cases']}`.",
                  "- Interrupted/invalid cases are reported separately and are never counted as safe.",
                  "", "## Canonical Run IDs", ""])
    lines.extend(f"- {suite}: `{run_id}`" for suite, run_id in campaign["canonical_run_ids"].items())
    lines.extend(["", "## Provenance", "", f"- Release: `{campaign['release']['release_id']}`", f"- Release SHA-256: `{campaign['release']['release_sha256']}`", f"- Source tree SHA-256: `{campaign['release']['source_tree_sha256']}`", f"- Dataset Pack v4 SHA-256: `{campaign['dataset_pack_v4_sha256']}`", "- Strict retry: only zero-behaviour infrastructure failures may resume; INVALID_MODEL_OUTPUT and INFRA_INTERRUPTED are terminal.", "- T353 retains primary, honest and manipulated replay branches and the corrected paired metric.", "- T361-T363 use the frozen auxiliary `glm-5.3-flash` / `sh-personas-1.0.0` profile and remain SIMULATION_ONLY.", "- Historical v3/v3.2 runs were not consumed and remain historical evidence only."])
    return "\n".join(lines) + "\n"


def collect_bundle_files(campaign_dir: Path, audit_path: Path, runs: dict, datasets: dict) -> list[Path]:
    files = [ROOT / "AGENTS.md", ROOT / "pyproject.toml", ROOT / "data/datasets/DATASET_PACK_v4.yaml",
             ROOT / "scripts/v4_1_6_finalize_campaign.py", audit_path]
    files.extend(p for p in (ROOT / "release").glob("*.json") if p.is_file())
    for base in ("src", "contracts", "config", "prompts"):
        files.extend(p for p in (ROOT / base).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend(campaign_dir / name for name in ("campaign.json", "report.md", "dashboard.html", "post-run-validation.json",
                                                   "campaign-acceptance.json", "pre-delivery-acceptance.json", "REPRODUCE.md"))
    for base in ("docs", "tests/v4"):
        files.extend(p for p in (ROOT / base).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend(p for p in (ROOT / "scripts").glob("v4*.py") if p.is_file())
    files.extend(p for p in (ROOT / "data/runs/_v4_1_6_manifests").glob("*.manifest.json") if p.is_file())
    for relative in ("state/PROJECT_STATE.yaml", "state/WORK_QUEUE.yaml", "state/SCIENTIFIC_CLOSURE_CHECKPOINT.md",
                     "state/DESIGN_DECISIONS.yaml", "docs/V4_CHANGELOG.md",
                     "artifacts/scientific_closure_v4/runtime-promotion-audit-v4.1.6-001.json",
                     "artifacts/scientific_closure_v4/run-manifest-registry-v4.1.6-001.json",
                     "artifacts/scientific_closure_v4/live-smoke/V4_1_6_S8_LIVE_SMOKE.json",
                     "artifacts/gates/V4_S7_RUNTIME_INTEGRATION_004.json",
                     "artifacts/gates/V4_S7_PROVIDER_APPROVAL_003.json"):
        path = ROOT / relative
        if path.is_file():
            files.append(path)
    for relative in ("tests/runtime/test_v4_strict_runtime.py", "tests/construct/test_synthetic_human_model.py"):
        path = ROOT / relative
        if path.is_file():
            files.append(path)
    for run in runs.values():
        run_dir = run["run_dir"]
        files.extend(p for p in run_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for item in datasets.values():
        files.extend(p for p in item["dataset_dir"].rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return sorted({p for p in files if p.is_file()}, key=lambda p: p.relative_to(ROOT).as_posix())


def write_bundle(campaign_dir: Path, files: list[Path], bundle_path: Path) -> tuple[dict, dict]:
    entries = []
    for path in files:
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_BYTES):
            raise ValueError(f"secret pattern found in bundle input: {path}")
        entries.append({"path": path.relative_to(ROOT).as_posix(), "size": len(data), "sha256": sha256_bytes(data), "crc32": f"{zlib.crc32(data) & 0xffffffff:08x}"})
    inventory = {"artifact": "V4_1_6_DELIVERY_INVENTORY", "entries": entries, "provider_calls": 0}
    inventory_path = campaign_dir / "delivery-inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(bundle_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (*files, inventory_path):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 10, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(bundle_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("bundle CRC verification failed")
        for info in archive.infolist():
            if info.filename == inventory_path.relative_to(ROOT).as_posix():
                continue
            expected = next(item for item in entries if item["path"] == info.filename)
            if f"{info.CRC:08x}" != expected["crc32"]:
                raise ValueError(f"bundle CRC mismatch: {info.filename}")
    manifest = {"artifact": "V4_1_6_FINAL_DELIVERY", "bundle": {"path": bundle_path.relative_to(ROOT).as_posix(), "sha256": sha256(bundle_path), "size_bytes": bundle_path.stat().st_size}, "inventory": ref(inventory_path), "secret_scan_clean": True, "crc_verified": True, "provider_calls": 0}
    return inventory, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding-audit", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--bundle-path", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_directory.resolve()
    bundle_path = args.bundle_path.resolve()
    if not destination.is_relative_to((ROOT / "artifacts").resolve()) or destination.exists():
        raise ValueError("output directory must be new and under artifacts")
    if not bundle_path.is_relative_to((ROOT / "artifacts").resolve()) or bundle_path.exists():
        raise ValueError("bundle path must be new and under artifacts")
    audit_path = args.binding_audit.resolve()
    audit = read_json(audit_path)
    release, release_path, release_sha = load_release()
    assert_audit(audit, release, release_sha)
    if source_tree_hash() != release["source_tree_sha256"]:
        raise ValueError("workspace source tree differs from the frozen Release")
    runs, datasets, suite_results = {}, {}, {}
    for row in audit["suites"]:
        run, dataset = validate_suite(row, release, release_sha)
        runs[row["suite"]], datasets[row["suite"]] = run, dataset
        suite_results[row["suite"]] = summarize(row["suite"], run)
    destination.mkdir(parents=True)
    suite_totals = {key: sum(value[key] for value in suite_results.values())
                    for key in ("invalid_model_output_cases", "infra_interrupted_cases", "recorded_model_responses")}
    campaign = {"artifact": "V4_1_6_CANONICAL_CAMPAIGN", "campaign_id": f"v4.1.6-canonical-{time.strftime('%Y%m%d-%H%M%S')}", "verdict": "STRICT_18_OF_18", "pass": True, "provider_calls": suite_totals["recorded_model_responses"],
                "release": {"release_id": release["release_id"], "release_sha256": release_sha, "source_tree_sha256": release["source_tree_sha256"]},
                "binding_audit": ref(audit_path), "tested_model_roster": ["deepseek-v4.1-flash"], "canonical_run_ids": {s: runs[s]["run_id"] for s in SUITES},
                "suite_results": suite_results, "cases": sum(v["cases"] for v in suite_results.values()), "simulation_only_suites": sorted(SIMULATION_ONLY),
                "historical_runs_consumed": 0, "safety_utility_separation": True, "source_tree_sha256": source_tree_hash(),
                "dataset_pack_v4_sha256": release["dataset_pack_v4_sha256"],
                "strict_retry_semantics": release["invalid_output_semantics"]["strict_retry_semantics"],
                "invalid_model_output_cases": suite_totals["invalid_model_output_cases"],
                "infra_interrupted_cases": suite_totals["infra_interrupted_cases"],
                "recorded_model_responses": suite_totals["recorded_model_responses"],
                "t353_paired_replay_corrected": True,
                "evidence": {s: datasets[s]["evidence"] + [ref(p) for p in sorted((runs[s]["run_dir"] / "attempts").rglob("attempt-*.jsonl"))] for s in SUITES}}
    (destination / "campaign.json").write_text(json.dumps(campaign, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "report.md").write_text(markdown_report(campaign), encoding="utf-8")
    (destination / "dashboard.html").write_text(html_dashboard(campaign), encoding="utf-8")
    (destination / "post-run-validation.json").write_text(json.dumps({"artifact": "V4_1_6_POST_RUN_VALIDATION", "release": campaign["release"], "binding_audit": ref(audit_path), "strict_count": audit["strict_count"], "total": audit["total_suites"], "pass": True, "provider_calls": 0, "suite_reports": audit["suites"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    campaign_acceptance = {"artifact": "V4_1_6_CANONICAL_CAMPAIGN_ACCEPTANCE", "verdict": "STRICT_18_OF_18", "pass": True, "release": campaign["release"], "canonical_suites": 18, "canonical_cases": 1620, "binding_audit": ref(audit_path), "post_run_validation": ref(destination / "post-run-validation.json"), "provider_calls": campaign["provider_calls"]}
    (destination / "campaign-acceptance.json").write_text(json.dumps(campaign_acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reproduce = "# Reproduce IoA-Bench v4.1.6\n\n1. Verify the Release, registry, inventory and bundle SHA-256 values.\n2. Run `python -B -X utf8 -m pytest tests/v4 -q -p no:cacheprovider`.\n3. Run `python -B -X utf8 scripts/v4_1_6_validate_run.py --all`.\n4. Run the strict binding audit and compare its Release identity with `campaign.json`.\n5. Inspect each Run Manifest, attempt journal and Replay hash before using a suite result.\n\nThe formal Campaign requires explicit AIHubMix authorization and must not be repeated to improve results. T361-T363 are SIMULATION_ONLY.\n"
    (destination / "REPRODUCE.md").write_text(reproduce, encoding="utf-8")
    pre_delivery = {"artifact": "V4_1_6_PRE_DELIVERY_ACCEPTANCE", "verdict": "STRICT_18_OF_18", "pass": True,
                    "release": campaign["release"], "canonical_suites": 18, "canonical_cases": 1620,
                    "binding_audit": ref(audit_path), "post_run_validation": ref(destination / "post-run-validation.json"),
                    "campaign": ref(destination / "campaign.json"), "campaign_acceptance": ref(destination / "campaign-acceptance.json"),
                    "secret_scan_clean": "pending_bundle_scan", "bundle_crc_verified": "pending_bundle_scan",
                    "provider_calls": campaign["provider_calls"]}
    (destination / "pre-delivery-acceptance.json").write_text(json.dumps(pre_delivery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = collect_bundle_files(destination, audit_path, runs, datasets)
    _, delivery = write_bundle(destination, files, bundle_path)
    (destination / "delivery-manifest.json").write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    final_acceptance = {"artifact": "V4_1_6_FINAL_PROJECT_ACCEPTANCE", "verdict": "PASS", "pass": True, "release": campaign["release"], "canonical_suites": 18, "canonical_cases": 1620, "binding_audit": ref(audit_path), "post_run_validation": ref(destination / "post-run-validation.json"), "campaign": ref(destination / "campaign.json"), "campaign_acceptance": ref(destination / "campaign-acceptance.json"), "delivery": ref(destination / "delivery-manifest.json"), "secret_scan_clean": delivery["secret_scan_clean"], "bundle_crc_verified": delivery["crc_verified"], "provider_calls": campaign["provider_calls"]}
    (destination / "final-project-acceptance.json").write_text(json.dumps(final_acceptance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (destination / "delivery-manifest.json", destination / "final-project-acceptance.json"):
        if any(pattern.search(path.read_bytes()) for pattern in SECRET_BYTES):
            raise ValueError(f"secret pattern found in final artifact: {path}")
    print(json.dumps({"pass": True, "canonical_suites": 18, "canonical_cases": 1620, "bundle": delivery["bundle"], "provider_calls": 0}, ensure_ascii=False))
    return 0


def source_tree_hash() -> str:
    from ioabench.runtime.full_manifest import source_tree_hash as hash_tree
    return hash_tree(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
