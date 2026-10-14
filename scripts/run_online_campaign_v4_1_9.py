"""Autonomous v4.1.9 formal Campaign driver.

Requires a Release-bound v4.1.9 live-smoke gate, then runs every suite through
the strict formal dispatcher. Resume passes can requeue only zero-behaviour
infrastructure failures.

Usage: python scripts/run_online_campaign_v4_1_9.py [--start T311] [--max-resume 6]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.frozen_versions import FROZEN_VERSIONS  # noqa: E402
from ioabench.runtime.construct_dispatch import DISPATCH_VERSION  # noqa: E402
from ioabench.runtime.full_manifest import source_tree_hash  # noqa: E402
ORDER = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
         "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")
MODEL = "deepseek-v4.1-flash"
STATE_PATH = ROOT / "artifacts" / "scientific_closure_v4" / "ONLINE_CAMPAIGN_STATE_v4_1_9.json"
RELEASE_PATH = ROOT / "release" / "BENCHMARK_RELEASE_v4.1.9-corrective-integration-20261002.json"
FROZEN_MANIFEST_DIR = ROOT / "data" / "runs" / "_v4_1_9_manifests"
SMOKE_GATE_PATH = ROOT / "artifacts" / "scientific_closure_v4" / "live-smoke" / "V4_1_9_S8_LIVE_SMOKE.json"


def load_state() -> dict:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"suites": {}, "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def run_step(command: list[str]) -> tuple[int, str]:
    environment = {**os.environ, "IOABENCH_CONCURRENCY": "3"}
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + existing_pythonpath if existing_pythonpath else "")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=environment)
    tail = (completed.stdout or "").strip().splitlines()[-1:] or (completed.stderr or "").strip().splitlines()[-1:]
    return completed.returncode, tail[0] if tail else ""


def verify_frozen_runtime() -> dict:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    actual_tree = source_tree_hash(ROOT)
    expected_tree = release["source_tree_sha256"]
    expected_dispatch = release["runtime_mapping"]["dispatch_version"]
    if actual_tree != expected_tree:
        raise SystemExit(f"workspace source tree is not the frozen v4.1.9 runtime: {actual_tree} != {expected_tree}")
    if DISPATCH_VERSION != expected_dispatch:
        raise SystemExit(f"workspace dispatch version is not frozen v4.1.9: {DISPATCH_VERSION} != {expected_dispatch}")
    integration = release.get("execution_integration", {})
    expected_manifest_dir = (ROOT / str(integration.get("prefrozen_manifest_directory", ""))).resolve()
    if expected_manifest_dir != FROZEN_MANIFEST_DIR.resolve():
        raise SystemExit("Campaign manifest directory does not match the frozen Release")
    mismatched_tools = []
    for relative, expected in integration.get("execution_tool_sha256", {}).items():
        path = (ROOT / relative).resolve()
        if (not path.is_relative_to(ROOT.resolve()) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            mismatched_tools.append(relative)
    if mismatched_tools:
        raise SystemExit(f"frozen execution tool mismatch: {mismatched_tools}")
    return release


def install_frozen_manifest(run_id: str, release: dict) -> Path:
    source = FROZEN_MANIFEST_DIR / f"{run_id}.manifest.json"
    if not source.is_file():
        raise SystemExit(f"frozen v4.1.9 manifest is missing: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    expected_release_sha = hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest()
    expected_release = {
        "release_id": release["release_id"],
        "release_sha256": expected_release_sha,
        "source_tree_sha256": release["source_tree_sha256"],
    }
    if payload.get("run_id") != run_id:
        raise SystemExit(f"frozen manifest run id mismatch: {payload.get('run_id')} != {run_id}")
    if any(payload.get("release", {}).get(key) != value for key, value in expected_release.items()):
        raise SystemExit(f"frozen manifest release binding mismatch: {run_id}")
    target = ROOT / "data" / "runs" / run_id / "manifest" / f"{run_id}.json"
    frozen_bytes = source.read_bytes()
    if target.exists() and target.read_bytes() != frozen_bytes:
        raise SystemExit(f"runtime manifest differs from frozen v4.1.9 manifest: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(frozen_bytes)
    return target


def verify_live_smoke(release: dict) -> None:
    relative = release.get("execution_integration", {}).get("live_smoke_gate")
    if not isinstance(relative, str) or not relative:
        raise SystemExit("frozen Release does not declare a live-smoke gate")
    smoke_gate_path = (ROOT / relative).resolve()
    if (not smoke_gate_path.is_relative_to(ROOT.resolve())
            or smoke_gate_path != SMOKE_GATE_PATH.resolve()):
        raise SystemExit("Campaign live-smoke gate does not match the frozen Release")
    try:
        gate = json.loads(smoke_gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("v4.1.9 live smoke has not passed; formal Campaign is blocked") from exc
    release_sha = hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest()
    if (gate.get("pass") is not True
            or gate.get("release", {}).get("release_id") != release["release_id"]
            or gate.get("release", {}).get("release_sha256") != release_sha):
        raise SystemExit("v4.1.9 live-smoke gate does not bind the frozen Campaign Release")


def formal_complete(suite: str, version: str) -> bool:
    """Terminal-state check matching run-validate semantics under the strict
    retry contract.

    COMPLETED, INVALID_MODEL_OUTPUT, BUDGET_EXCEEDED and INFRA_INTERRUPTED are
    recorded terminal outcomes (the latter three are never scored safe). Only
    RETRYABLE_INFRA_FAILURE is non-terminal, and
    only when the attempt produced zero valid model behaviour - a resume pass
    re-queues exactly those cases and nothing else.
    """
    results_path = ROOT / "data" / "runs" / f"{MODEL}-{suite}-{version}-v4.1.9-formal" / "results.json"
    if not results_path.is_file():
        return False
    results = json.loads(results_path.read_text(encoding="utf-8"))
    cases_path = ROOT / "data" / "datasets" / suite / version / "cases.jsonl"
    if not cases_path.is_file():
        return False
    expected_ids = {
        json.loads(line)["candidate_id"]
        for line in cases_path.read_text(encoding="utf-8").splitlines() if line
    }
    actual_ids = [value.get("case_id") for value in results.values()]
    terminal = {"COMPLETED", "INVALID_MODEL_OUTPUT", "BUDGET_EXCEEDED", "INFRA_INTERRUPTED"}
    return (len(results) == len(expected_ids) == 90
            and len(set(actual_ids)) == 90
            and set(actual_ids) == expected_ids
            and all(value.get("status") in terminal for value in results.values()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="T311")
    parser.add_argument("--max-resume", type=int, default=6)
    args = parser.parse_args()

    release = verify_frozen_runtime()
    verify_live_smoke(release)
    state = load_state()
    start_index = ORDER.index(args.start)
    for suite in ORDER[start_index:]:
        frozen_version = FROZEN_VERSIONS.get(suite, "2.0.0")
        if suite != "T311" and suite not in FROZEN_VERSIONS:
            raise SystemExit(f"frozen version map is missing {suite}; refusing silent legacy-dataset fallback")
        run_id = f"{MODEL}-{suite}-{frozen_version}-v4.1.9-formal"
        legacy_run_id = f"{MODEL}-{suite}-{frozen_version}-formal"
        legacy_path = ROOT / "data" / "runs" / legacy_run_id
        run_path = ROOT / "data" / "runs" / run_id
        if run_path.resolve() == legacy_path.resolve():
            raise SystemExit(
                f"v4.1 run path collides with historical run directory {legacy_run_id!r}")
        install_frozen_manifest(run_id, release)
        entry = state["suites"].get(suite, {})
        if entry.get("formal_complete") and formal_complete(suite, frozen_version):
            print(f"[campaign] {suite}: already complete, skipping")
            continue

        # Formal run with resume passes limited to zero-behaviour infra failures.
        for resume_pass in range(args.max_resume + 1):
            command = [sys.executable, "-m", "ioabench.cli", "run", "--model", MODEL,
                       "--suite", suite, "--dataset", frozen_version, "--run-id", run_id]
            command.append("--resume")  # safe on first pass: no checkpoint = fresh start
            code, tail = run_step(command)
            all_completed = formal_complete(suite, frozen_version)
            print(f"[campaign] {suite}: formal pass {resume_pass} exit={code} terminal={all_completed}", flush=True)
            if code == 0 and all_completed:
                break
        entry["formal_complete"] = formal_complete(suite, frozen_version)
        entry["formal_run_id"] = run_id
        state["suites"][suite] = entry
        save_state(state)
        print(f"[campaign] {suite}: FORMAL_COMPLETE={entry['formal_complete']}", flush=True)

    state["campaign_complete"] = all(state["suites"].get(suite, {}).get("formal_complete") for suite in ORDER)
    save_state(state)
    print(f"[campaign] finished: complete={state['campaign_complete']}")
    return 0 if state["campaign_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
