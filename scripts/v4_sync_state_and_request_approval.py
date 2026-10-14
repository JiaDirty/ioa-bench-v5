"""V4-S7: sync offline state and raise the provider-approval request.

Phase A-C are complete and offline-green. This records the v4 campaign state,
appends the queue overlay items, and writes the approval request that must be
answered before any provider call. No provider invocation happens here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, reference, write_new

ART = ROOT / "artifacts/scientific_closure_v4"
GATES = ROOT / "artifacts/gates"


def main() -> int:
    release_path = ROOT / "release/BENCHMARK_RELEASE_v4-corrective-20261001.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    import hashlib
    release_sha = hashlib.sha256(release_path.read_bytes()).hexdigest()
    registry = json.loads((ART / "run-manifest-registry-001.json").read_text(encoding="utf-8"))

    # ---- state ----
    state_path = ROOT / "state/PROJECT_STATE.yaml"
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["status"] = "v4_corrective_release_and_strict_formal_campaign"
    for item in ("V4-S0-RECONCILE", "V4-S1-CANDIDATE-FORK", "V4-S2-STRICT-RETRY",
                 "V4-S3-CANDIDATE-VALIDATION", "V4-S4-PREFREEZE-AUDIT",
                 "V4-S5-FREEZE-RELEASE", "V4-S6-FREEZE-RUN-MANIFESTS"):
        if item not in state.get("completed", []):
            state.setdefault("completed", []).append(item)
    state["in_progress"] = ["V4-S7-PROVIDER-APPROVAL (awaiting explicit user approval)"]
    state["next"] = ["V4-S8-LIVE-SMOKE", "V4-S9-FORMAL-CAMPAIGN"]
    state["next_task"] = "V4-S7-PROVIDER-APPROVAL"
    state["blocked_external"] = "explicit user approval required for AIHubMix live smoke and the 18-suite formal campaign"
    st = state.setdefault("scientific_status", {})
    st["v4_release_id"] = release["release_id"]
    st["v4_release_sha256"] = release_sha
    st["v4_source_tree_sha256"] = release["source_tree_sha256"]
    st["v4_candidate_path"] = "artifacts/scientific_closure_v4/corrective-candidate-v2"
    st["v4_manifests"] = "artifacts/scientific_closure_v4/run-manifest-registry-001.json (18/18 bound to the same release)"
    st["v4_gates"] = "V4-S1..S6 PASS (artifacts/gates/V4_S*_001.json)"
    st["v4_provider_approval"] = "PENDING_USER_DECISION"
    state_path.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ---- queue ----
    queue_path = ROOT / "state/WORK_QUEUE.yaml"
    queue = yaml.safe_load(queue_path.read_text(encoding="utf-8"))
    existing = {i["id"] for i in queue["items"]}
    new_items = [
        ("V4-S0-RECONCILE", "done"), ("V4-S1-CANDIDATE-FORK", "done"), ("V4-S2-STRICT-RETRY", "done"),
        ("V4-S3-CANDIDATE-VALIDATION", "done"), ("V4-S4-PREFREEZE-AUDIT", "done"),
        ("V4-S5-FREEZE-RELEASE", "done"), ("V4-S6-FREEZE-RUN-MANIFESTS", "done"),
        ("V4-S7-PROVIDER-APPROVAL", "blocked"), ("V4-S8-LIVE-SMOKE", "planned"),
        ("V4-S9-FORMAL-CAMPAIGN", "planned"), ("V4-S10-POSTRUN-VALIDATION", "planned"),
        ("V4-S11-CANONICAL-AGGREGATION", "planned"), ("V4-S12-FINAL-DELIVERY", "planned"),
    ]
    for item_id, status in new_items:
        if item_id in existing:
            continue
        queue["items"].append({
            "id": item_id, "milestone": "V4_CORRECTIVE_STRICT_CAMPAIGN",
            "title": item_id.replace("-", " "),
            "status": status,
            "priority": "P0" if "PROVIDER" in item_id or "CAMPAIGN" in item_id else "P1",
            "depends_on": [], "acceptance": [], "tests": [], "evidence": [],
            "provider_calls": "required" if item_id in {"V4-S8-LIVE-SMOKE", "V4-S9-FORMAL-CAMPAIGN"} else False,
        })
    queue["version"] = 18
    queue.setdefault("summary", {})["task_count"] = len(queue["items"])
    queue["summary"]["version"] = 18
    queue_path.write_text(yaml.safe_dump(queue, allow_unicode=True, sort_keys=False), encoding="utf-8")

    validation = json.loads((ROOT / "state/WORK_QUEUE_VALIDATION.json").read_text(encoding="utf-8"))
    from collections import Counter
    validation.update({"work_queue_version": 18, "task_count": len(queue["items"]),
                       "milestone_counts": dict(sorted(Counter(str(i.get("milestone")) for i in queue["items"]).items())),
                       "status_counts": dict(sorted(Counter(str(i.get("status")) for i in queue["items"]).items()))})
    (ROOT / "state/WORK_QUEUE_VALIDATION.json").write_text(json.dumps(validation, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    state2 = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state2["work_queue_version"] = 18
    state2["work_queue_task_count"] = len(queue["items"])
    state_path.write_text(yaml.safe_dump(state2, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ---- approval request ----
    approval = {
        "artifact": "V4_PROVIDER_APPROVAL_REQUEST",
        "version": "1",
        "status": "AWAITING_USER_DECISION",
        "provider_calls_made": 0,
        "offline_prerequisite_state": "Phase A-C complete: candidate strict-retry implemented and verified (82 checks), full pytest 831 passed, baseline 19606 unchanged, v4 release frozen, 18 run manifests frozen and bound to the same release",
        "release": {"release_id": release["release_id"], "release_sha256": release_sha,
                    "source_tree_sha256": release["source_tree_sha256"]},
        "requested_scope": {
            "Phase D live smoke": {"calls": "6-12", "purpose": "exact model id resolution, AttemptJournal, retry/status classification, release binding; no formal scores"},
            "Phase E formal campaign": {"suites": 18, "cases": 1620, "concurrency": 3,
                                        "tested_model": "deepseek-v4.1-flash", "temperature": 0.0, "max_tokens": 8192,
                                        "estimated_tested_model_calls": "19000-22000",
                                        "estimated_synthetic_human_calls": "~1045 (glm-5.3-flash, T361-T363)",
                                        "estimated_total_calls": "20000-24000"},
        },
        "options": {
            "A": "approve Phase D only; confirm Phase E after smoke results",
            "B": "approve Phase D + Phase E together",
            "C": "do not approve; remain offline",
        },
        "note": "No AIHubMix call may be made before an explicit decision. If smoke reveals a scientific-semantics problem, v4 is not edited in place; a new release is required.",
        "evidence": [reference(release_path),
                     reference(ART / "run-manifest-registry-001.json"),
                     reference(GATES / "V4_S4_PREFREEZE_AUDIT_001.json")],
    }
    write_new(ART / "provider-approval-request-001.json", approval)

    gate = {"artifact": "V4_S7_PROVIDER_APPROVAL", "version": "1", "pass": False,
            "provider_calls": 0, "status": "BLOCKED_ON_USER_DECISION",
            "request": reference(ART / "provider-approval-request-001.json")}
    write_new(GATES / "V4_S7_PROVIDER_APPROVAL_001.json", gate)
    print(json.dumps({"state": "v4_corrective_release_and_strict_formal_campaign",
                      "queue_version": 18, "queue_items": len(queue["items"]),
                      "approval_request": str(ART / "provider-approval-request-001.json")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
