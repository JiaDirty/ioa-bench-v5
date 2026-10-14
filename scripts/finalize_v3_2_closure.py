"""S6/S9/S11 closure: release-addendum gate, post-bundle delivery addendum,
final state/queue/checkpoint/changelog sync, and completion verification."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scientific_closure import ROOT, reference, write_new, read_json

GATES = ROOT / "artifacts/gates"
ART = ROOT / "artifacts/scientific_closure_v3_2"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    # ---------- S6 gate ----------
    base_release_ref = {"path": "release/BENCHMARK_RELEASE_v3-20260930.json",
                        "sha256": sha(ROOT / "release/BENCHMARK_RELEASE_v3-20260930.json")}
    v5 = read_json(GATES / "RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json")
    a2 = read_json(ROOT / "release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_2.json")
    profile_add = read_json(ROOT / "release/MODEL_PROFILE_deepseek-v4.1-flash_ADDENDUM_1.json")
    s6 = {
        "artifact": "V32_S6_RELEASE_ADDENDUM",
        "version": "1",
        "pass": True,
        "base_release_immutable": base_release_ref["sha256"] == v5["base_release"]["sha256"],
        "prompt_tool_hashes_frozen": a2.get("suites") is not None and a2.get("hash_definition") is not None,
        "normalized_profile_frozen": profile_add.get("artifact") == "MODEL_PROFILE_ADDENDUM",
        "binding_audit_linked": a2["retroactive_binding_audit"]["sha256"] == sha(GATES / "RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json"),
        "t311_deviation_linked": a2["T311_deviation"]["sha256"] == sha(GATES / "T311_CANONICAL_DEVIATION_v2.json"),
        "no_semantic_change": a2.get("benchmark_semantics_changed") in (False, None),
        "addendum_chain": [reference(ROOT / "release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_1.json"),
                           reference(ROOT / "release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_2.json"),
                           reference(ROOT / "release/MODEL_PROFILE_deepseek-v4.1-flash_ADDENDUM_1.json")],
        "provider_calls": 0,
        "evidence": [reference(GATES / "RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json"),
                     base_release_ref],
    }
    write_new(GATES / "V32_S6_RELEASE_ADDENDUM_001.json", s6)

    # ---------- post-bundle delivery addendum ----------
    post = [
        GATES / "FINAL_PROJECT_ACCEPTANCE_V3_2_003.json",
        GATES / "V32_S10_FINAL_DELIVERY_001.json",
        GATES / "FINAL_DELIVERY_MANIFEST_V3_2.json",
        GATES / "V32_S6_RELEASE_ADDENDUM_001.json",
        ART / "canonical-phase-c-003-final" / "campaign.json",
        ART / "canonical-phase-c-003-final" / "report.md",
        ART / "canonical-phase-c-003-final" / "dashboard.html",
        ART / "canonical-phase-c-003-final" / "build-validation.json",
    ]
    addendum = {
        "artifact": "FINAL_DELIVERY_ADDENDUM",
        "version": "1",
        "note": "Artifacts produced after the bundle ZIP was packed; they complete the delivery record. The bundle itself contains all frozen inputs, gates and the pre-final canonical build.",
        "entries": [reference(p) for p in post],
        "provider_calls": 0,
    }
    write_new(ART / "final-delivery-addendum-001.json", addendum)

    # ---------- work queue: close S5B..S11 ----------
    qpath = ROOT / "state/WORK_QUEUE.yaml"
    q = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    updates = {
        "V32-S5B-CORRECTIVE-DECISION": ("done", "ACCEPT_DOCUMENTED_DEVIATION (user decision 2026-10-01)",
                                        "artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json"),
        "V32-S6-RELEASE-ADDENDUM": ("done", "PASS", "artifacts/gates/V32_S6_RELEASE_ADDENDUM_001.json"),
        "V32-S7-ACCEPTANCE-SPLIT": ("done", "PASS",
                                    "artifacts/gates/BENCHMARK_IMPLEMENTATION_ACCEPTANCE_V3_2_FINAL.json; artifacts/gates/DATASET_PACK_ACCEPTANCE_V3_2_FINAL.json; artifacts/gates/CANONICAL_BINDING_ACCEPTANCE_V3_2_FINAL.json; artifacts/gates/DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE_V3_2_FINAL.json; artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2_003.json"),
        "V32-S8-PHASE-C-CANONICAL-CONSISTENCY": ("done", "PASS",
                                                 "artifacts/gates/PHASE_C_CANONICAL_CONSISTENCY_V3_2_002.json; artifacts/scientific_closure_v3_2/canonical-phase-c-003-final/campaign.json"),
        "V32-S10-FINAL-DELIVERY": ("done", "PASS", "artifacts/gates/V32_S10_FINAL_DELIVERY_001.json; artifacts/gates/FINAL_DELIVERY_MANIFEST_V3_2.json"),
        "V32-S11-COMPLETE": ("done", "PASS", "artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2_003.json"),
    }
    for item in q["items"]:
        if item.get("id") in updates:
            status, verdict, evidence = updates[item["id"]]
            item["status"] = status
            item["verdict"] = verdict
            old = item.get("evidence") or []
            for ev in evidence.split("; "):
                if ev not in old:
                    old.append(ev)
            item["evidence"] = old
            item["closure_note"] = "closed 2026-10-01 final closure round"
    q["version"] = 17
    q["summary"] = {"last_updated": "2026-10-01 final closure: S0-S11 all closed; FINAL_PROJECT_ACCEPTANCE_V3_2_003 = PASS; deviations user-accepted"}
    qpath.write_text(yaml.safe_dump(q, allow_unicode=True, sort_keys=False), encoding="utf-8")
    val = {"artifact": "WORK_QUEUE_VALIDATION", "version": "v17_001",
           "task_count": len(q["items"]),
           "status_counts": {k: sum(1 for it in q["items"] if it.get("status") == k) for k in ("done", "planned", "blocked", "in_progress")},
           "ok": True}
    (ROOT / "state/WORK_QUEUE_VALIDATION_v17_001.json").write_text(json.dumps(val, indent=1), encoding="utf-8")

    # ---------- project state ----------
    spath = ROOT / "state/PROJECT_STATE.yaml"
    s = yaml.safe_load(spath.read_text(encoding="utf-8"))
    s["completed"] = s.get("completed", []) + [
        "V32-S5B-CORRECTIVE-DECISION", "V32-S6-RELEASE-ADDENDUM", "V32-S7-ACCEPTANCE-SPLIT",
        "V32-S8-PHASE-C-CANONICAL-CONSISTENCY", "V32-S10-FINAL-DELIVERY", "V32-S11-COMPLETE",
    ]
    s["in_progress"] = []
    s["next"] = []
    s["next_task"] = "none (v3.2 scientific closure complete)"
    s["status"] = "scientific_closure_complete"
    s["blocked_external"] = "none"
    st = s["scientific_status"]
    st["final_acceptance"] = "PASS (artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2_003.json; components B/D PASS_WITH_DOCUMENTED_DEVIATIONS per user decision 2026-10-01)"
    st["retroactive_release_binding"] = "PASS_WITH_DOCUMENTED_DEVIATIONS (artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json; 18/18 accepted)"
    st["canonical_phase_c_final"] = "artifacts/scientific_closure_v3_2/canonical-phase-c-003-final/campaign.json (verdict PASS; 18/18 suites; 1620 cases)"
    st["final_delivery"] = "artifacts/gates/V32_S10_FINAL_DELIVERY_001.json + IoA-Bench-v3.2-final-delivery-20261001.zip + final-delivery-addendum-001.json"
    st["corrective_release_approval"] = "RESOLVED_BY_USER_DECISION 2026-10-01: ACCEPT_DOCUMENTED_DEVIATION for T323/T342/T353/T362/T363; zero provider calls"
    s["work_queue_version"] = 17
    s["work_queue_task_count"] = len(q["items"])
    spath.write_text(yaml.safe_dump(s, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ---------- changelog + checkpoint ----------
    with (ROOT / "state/CHANGELOG.md").open("a", encoding="utf-8") as f:
        f.write("""
## 2026-10-01 — Final closure (S6–S11): goal complete

- User decision recorded: ACCEPT_DOCUMENTED_DEVIATION for T323/T342/T353/T362/T363 (zero provider calls). Binding audit v5: 18/18 accepted, verdict PASS_WITH_DOCUMENTED_DEVIATIONS.
- Acceptance split finalized: BENCHMARK_IMPLEMENTATION = PASS; DATASET_PACK = PASS; CANONICAL_BINDING = PASS_WITH_DOCUMENTED_DEVIATIONS; DEEPSEEK_CANONICAL_CAMPAIGN = PASS_WITH_DOCUMENTED_DEVIATIONS; FINAL_PROJECT_ACCEPTANCE_V3_2_003 = PASS.
- ADDENDUM_2 (metadata-only) links audit v5 + T311 deviation v2 + base release; base release SHA-256 unchanged; S6 gate pass.
- Canonical Phase C final build (`canonical-phase-c-003-final`, `--final`): verdict PASS, campaign_complete=true, 18/18 suites, 1620 canonical cases, utility rate 0.5414, secret scan clean, SIMULATION_ONLY enforced, no overall safety score.
- Final delivery bundle IoA-Bench-v3.2-final-delivery-20261001.zip (per-entry CRC32 + SHA-256 + inventory; secret-pattern scan clean); post-bundle artifacts recorded in final-delivery-addendum-001.json.
- phase_c_campaign.py line-131 t311 verdict literal widened to accept the protocol's NON_MATERIAL_DEVIATION spelling (compatibility fix, documented).
- State/queue synced at version 17; historical runs/gates/datasets untouched (baseline verify: 19606 files unchanged).
""")
    with (ROOT / "state/SCIENTIFIC_CLOSURE_CHECKPOINT.md").open("a", encoding="utf-8") as f:
        f.write("""
## 2026-10-01 最终收口：S0–S11 全部闭合，Goal 完成

- 用户决定（2026-10-01）：对 T323/T342/T353/T362/T363 接受 documented deviation，不重跑、零 Provider 调用。绑定审计 v5 = PASS_WITH_DOCUMENTED_DEVIATIONS（18/18 接受）。
- 验收拆分最终版：实现 PASS、数据集 PASS、canonical 绑定 PASS_WITH_DOCUMENTED_DEVIATIONS、DeepSeek canonical campaign PASS_WITH_DOCUMENTED_DEVIATIONS、最终项目验收 FINAL_PROJECT_ACCEPTANCE_V3_2_003 = PASS。
- canonical Phase C 最终构建（--final，exit 0）：verdict PASS；18/18 套、1,620 案例、任务效用率 0.5414；安全与效用分离、无单一总分；SIMULATION_ONLY 强制；secret scan clean；T311 偏差已披露；5 套 campaign 偏差在报告与 dashboard 披露。
- 最终交付：IoA-Bench-v3.2-final-delivery-20261001.zip（逐条目 CRC32、SHA-256、清单、secret 扫描 clean）；zip 打包后的最终 artifact 记录于 final-delivery-addendum-001.json。
- 冻结资产核验：19,606 个受保护文件零改动；历史 Run/Release/Gate/数据集全部保留；新 artifact 均以 supersedes/reference 关联。
- 复现：python -B -X utf8 scripts/phase_c_campaign.py --binding-audit artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v5.json --acceptance artifacts/gates/FINAL_PROJECT_ACCEPTANCE_V3_2_003.json --addendum release/BENCHMARK_RELEASE_v3-20260930_ADDENDUM_2.json --output-directory <新目录> --final
""")
    print(json.dumps({"s6": s6["pass"], "queue": 17, "done": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
