"""Authoritative state reconciliation for the IoA-Bench online campaign.

Derives per-suite lifecycle evidence from immutable research assets on disk
(frozen dataset manifests, B5 pilot gates, formal-run results) and rewrites:

- state/WORK_QUEUE.yaml   per-suite V2-B-* statuses (+ V2-C readiness)
- state/PROJECT_STATE.yaml status / suite_lifecycle / blocked_external lines
- artifacts/gates/STATE_RECONCILIATION.json  evidence report

ONLINE_CAMPAIGN_STATE.json is NOT written here: the campaign driver owns that
file while running; rebuild it only after the driver has exited.

Usage: python scripts/reconcile_state.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
MODEL = "deepseek-v4.1-flash"
ORDER = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
         "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")

# authoritative frozen versions (kept in sync with run_online_campaign.py /
# run_online_pilot.py / tests/construct/test_formal_dispatcher.py)
from ioabench.frozen_versions import FROZEN_VERSIONS  # single source of truth

TERMINAL = {"COMPLETED", "INVALID_MODEL_OUTPUT"}


def suite_evidence(suite: str) -> dict:
    version = FROZEN_VERSIONS[suite]
    dataset = ROOT / "data" / "datasets" / suite / version
    ev: dict = {"suite": suite, "dataset_version": version, "dataset_frozen": False,
                "pilot_pass": False, "formal_complete": False,
                "formal_units": 0, "outcome_classes": {}, "eligibility": {}}
    manifest_path = dataset / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cases = [line for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        ev["dataset_frozen"] = True
        ev["dataset_cases"] = len(cases)
        ev["dataset_unique_ids"] = len({json.loads(c)["candidate_id"] for c in cases})
        ev["dataset_content_sha256"] = manifest.get("content_sha256") or manifest.get("cases_sha256")
        ev["quality_gates"] = manifest.get("quality_gates")
    gate_path = ROOT / "artifacts" / "gates" / f"{suite}_B5_PILOT.json"
    if gate_path.is_file():
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        ev["pilot_pass"] = gate.get("pass") is True
        ev["pilot_run_id"] = gate.get("run_id")
        disclosure = gate.get("recalculation_disclosure")
        if disclosure:
            ev["pilot_recalculation"] = disclosure.get("reason")
    results_path = ROOT / "data" / "runs" / f"{MODEL}-{suite}-{version}-formal" / "results.json"
    if results_path.is_file():
        results = json.loads(results_path.read_text(encoding="utf-8"))
        ev["formal_units"] = len(results)
        ev["formal_complete"] = bool(results) and all(v.get("status") in TERMINAL for v in results.values())
        for value in results.values():
            outcome = (value.get("score") or {}).get("outcome_class") or "?"
            ev["outcome_classes"][outcome] = ev["outcome_classes"].get(outcome, 0) + 1
            eligibility = value.get("eligibility") or "?"
            ev["eligibility"][eligibility] = ev["eligibility"].get(eligibility, 0) + 1
        ev["formal_run_id"] = f"{MODEL}-{suite}-{version}-formal"
    if ev["dataset_frozen"]:
        ev["lifecycle"] = ("FORMAL_EVALUATION_COMPLETE" if ev["formal_complete"]
                           else "PILOT_PASS_PILOT_GATE_RECORDED" if ev["pilot_pass"]
                           else "FORMAL_DATASET_FROZEN")
    else:
        ev["lifecycle"] = "DATASET_MISSING"
    return ev


def set_queue_status(queue_text: str, task_id: str, status: str) -> tuple[str, bool]:
    pattern = re.compile(r"(- id: %s\n(?:  .*\n)*?  status: )(\S+)" % re.escape(task_id))
    new_text, count = pattern.subn(lambda m: m.group(1) + status, queue_text, count=1)
    return new_text, count == 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    evidence = [suite_evidence(suite) for suite in ORDER]
    report = {"artifact": "STATE_RECONCILIATION",
              "rebuilt_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "tested_model": MODEL,
              "frozen_versions": FROZEN_VERSIONS,
              "suites": evidence}

    complete = [e["suite"] for e in evidence if e["lifecycle"] == "FORMAL_EVALUATION_COMPLETE"]
    pilot_passed = [e["suite"] for e in evidence if e["pilot_pass"]]
    report["summary"] = {
        "formal_complete": complete,
        "pilot_pass": pilot_passed,
        "campaign_complete": len(complete) == 18,
        "datasets_frozen_18": all(e["dataset_frozen"] and e.get("dataset_unique_ids") == e.get("dataset_cases") for e in evidence)}

    queue_path = ROOT / "state" / "WORK_QUEUE.yaml"
    queue_text = queue_path.read_text(encoding="utf-8")
    queue_changed: list[str] = []
    for ev in evidence:
        suite = ev["suite"]
        # prerequisites of a frozen formal dataset are implied by the freeze itself
        frozen = ev["dataset_frozen"] and ev.get("dataset_unique_ids") == ev.get("dataset_cases")
        updates = [
            (f"V2-B-{suite}-TRIAL_GENERATION", "done" if frozen else "blocked"),
            (f"V2-B-{suite}-RECIPE_VALIDATED", "done" if frozen else "blocked"),
            (f"V2-B-{suite}-FORMAL_DATASET_FROZEN", "done" if frozen else "blocked"),
            (f"V2-B-{suite}-ONLINE_PILOT", "done" if ev["pilot_pass"] else "blocked"),
            (f"V2-B-{suite}-ONLINE_PILOT_PASS", "done" if ev["pilot_pass"] else "blocked"),
            (f"V2-B-{suite}-FORMAL_RUN", "done" if ev["formal_complete"] else "blocked"),
            (f"V2-B-{suite}-FORMAL_EVALUATION_COMPLETE", "done" if ev["formal_complete"] else "blocked"),
        ]
        for task_id, status in updates:
            queue_text, ok = set_queue_status(queue_text, task_id, status)
            if ok:
                queue_changed.append(f"{task_id}->{status}")
            else:
                print(f"WARN: task block not found for {task_id}")
    campaign_all_done = len(complete) == 18
    gates = ROOT / "artifacts" / "gates"
    def _gate_done(name: str) -> bool:
        path = gates / name
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return bool(data.get("campaign_complete") or data.get("pass") or data.get("verdict") == "complete"
                    or data.get("verdict") == "PASS")
    # V2-C evidence artifacts exist and pass -> the queue reflects completion
    c_status = ("done" if campaign_all_done and _gate_done("PHASE_C_CAMPAIGN.json") else
                "ready" if campaign_all_done else "blocked")
    for task_id, status in (("V2-C01-CAMPAIGN-MANIFEST", c_status),
                            ("V2-C02-AGGREGATE-ANALYSIS", c_status),
                            ("V2-C03-DASHBOARD-REPORT", c_status),
                            ("V2-C04-REPRODUCIBILITY-BUNDLE", c_status),
                            ("V2-C05-FINAL-SCIENTIFIC-ACCEPTANCE",
                             "done" if _gate_done("FINAL_SCIENTIFIC_ACCEPTANCE.json") else c_status)):
        queue_text, ok = set_queue_status(queue_text, task_id, status)
        if ok:
            queue_changed.append(f"{task_id}->{status}")

    state_path = ROOT / "state" / "PROJECT_STATE.yaml"
    state_text = state_path.read_text(encoding="utf-8")
    state_changed: list[str] = []

    def replace_line(pattern: str, replacement: str) -> None:
        nonlocal state_text
        new_text, count = re.subn(pattern, replacement, state_text, count=1, flags=re.M)
        if count != 1:
            print(f"WARN: PROJECT_STATE anchor not matched: {pattern}")
            return
        if new_text != state_text:
            state_changed.append(replacement.strip()[:90])
        state_text = new_text

    replace_line(r"^status: \S+.*$",
                 "status: phase_b_online_campaign_in_progress" if not campaign_all_done
                 else "status: phase_b_campaign_complete_phase_c_ready")
    replace_line(r"^blocked_external: .*\.+\n|^blocked_external: .*$",
                 "blocked_external: none (AIHUBMIX_API_KEY available via workspace .env; online campaign running)")
    for ev in evidence:
        suite = ev["suite"]
        lifecycle = ev["lifecycle"]
        detail = f"({ev['dataset_version']}" + (
            f"; {ev['formal_units']}/90 terminal" if lifecycle == "FORMAL_EVALUATION_COMPLETE" else "")
        detail += ")"
        replace_line(rf"^  {suite}: FORMAL_[^\n]*$", f"  {suite}: {lifecycle} {detail}")

    if args.dry_run:
        print("[dry-run] queue changes:", len(queue_changed), "state changes:", len(state_changed))
        for item in queue_changed[:20]:
            print("  ", item)
        return 0

    queue_path.write_text(queue_text, encoding="utf-8")
    state_path.write_text(state_text, encoding="utf-8")
    report["queue_updates"] = queue_changed
    report["project_state_updates"] = state_changed
    out = ROOT / "artifacts" / "gates" / "STATE_RECONCILIATION.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"reconciled: {len(complete)}/18 formal complete; queue updates: {len(queue_changed)}; "
          f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
