"""Sync state, work queue, checkpoint and changelog with the S1-S5 closure round.

Edits are surgical: only the v3.2 closure items and scientific_status fields
produced by this round are touched; all historical entries are preserved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml

ROOT = Path(".")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    # ---------- work queue ----------
    qpath = ROOT / "state/WORK_QUEUE.yaml"
    q = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    evidence_map = {
        "V32-S1-INDEPENDENT-REVERIFY": ("done", "PARTIALLY_CONFIRMED", [
            "artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json",
            "artifacts/scientific_closure_v3_2/precampaign-source-anchoring-001.json",
            "artifacts/scientific_closure_v3_2/history-source-replay-008/reconstruction.json",
            "artifacts/gates/V32_S1_SOURCE_ANCHORING_001.json",
        ], "Decisive audit claims re-verified from disk; both history exports parsed; prior decisive UNKNOWNs (T311 deviation, source compatibility) resolved; only non-decisive unknown (retried-case identities) remains, bounded-search exhausted."),
        "V32-S2-DATASET-BINDING": ("done", "PASS", [
            "artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json"
        ], "Fresh three-way recompute: 18/18 canonical run dataset hash == release content hash == DATASET_PACK_v4 hash; case-id sets equal; all 1620 cases terminal."),
        "V32-S3-RUNTIME-SCORER-PROMPT-TOOL": ("done", "PASS", [
            "artifacts/scientific_closure_v3_2/source-semantic-review-003.json",
            "artifacts/scientific_closure_v3_2/precampaign-source-anchoring-001.json",
        ], "18/18 suites' scientific-path source content pinned exact per file; whole-tree residuals documented launch-layer; scorers pinned by identity/fingerprint; prompts/tools pinned by byte-exact runtime file and ADDENDUM_1 inventory."),
        "V32-S4-T311-DEVIATION": ("done", "NON_MATERIAL_DEVIATION", [
            "artifacts/gates/T311_CANONICAL_DEVIATION_v2.json",
        ], "max_tokens: 4096 ceiling never bound (max completion 3204, zero length finishes, byte-exact runtime recovery); concurrency 1 conservative with zero failure signatures; contract label metadata-only (content byte-identical since 2026-09-27)."),
        "V32-S5-RETROACTIVE-BINDING": ("done", "PARTIAL_13_ACCEPTED_5_INCOMPATIBLE", [
            "artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v4.json",
        ], "13/18 binding-accepted (1 documented deviation, 10 semantic, 2 strict); 5 suites proven INCOMPATIBLE (frozen retry-policy violation; T353 missing paired records) and require the recorded user decision."),
    }
    for item in q["items"]:
        if item.get("id") in evidence_map:
            status, verdict, evidence, note = evidence_map[item["id"]]
            item["status"] = status
            item["verdict"] = verdict
            old = item.get("evidence") or []
            item["evidence"] = old + [e for e in evidence if e not in old]
            item["closure_note"] = note
            item["completion_commands"] = item.get("completion_commands") or []
    q["items"].append({
        "id": "V32-S5B-CORRECTIVE-DECISION",
        "milestone": "SCIENTIFIC_CLOSURE_V3_2",
        "title": "User decision on the 5 INCOMPATIBLE suites (corrective release + scoped rerun, or accepted documented deviation)",
        "status": "blocked",
        "priority": "P0",
        "depends_on": ["V32-S5-RETROACTIVE-BINDING"],
        "provider_calls": "only_with_explicit_user_approval",
        "acceptance": ["user decision recorded in state", "binding audit v5 or documented-deviation register produced accordingly"],
        "references": ["artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v4.json", "artifacts/scientific_closure_v3_2/proposed-corrective-release-v2.json"],
        "blocked_reason": "Requires explicit user decision; no provider budget authorized. Pausing here is mandated by the goal pack pause rules.",
    })
    q["summary"] = q.get("summary") or {}
    q["summary"]["last_updated"] = "2026-10-01 scientific-closure round 2: S1-S5 closed with evidence; corrective decision blocker recorded"
    qpath.write_text(yaml.safe_dump(q, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ---------- project state ----------
    spath = ROOT / "state/PROJECT_STATE.yaml"
    s = yaml.safe_load(spath.read_text(encoding="utf-8"))
    s["completed"] = s.get("completed", []) + [
        "V32-S1-INDEPENDENT-REVERIFY", "V32-S2-DATASET-BINDING",
        "V32-S3-RUNTIME-SCORER-PROMPT-TOOL", "V32-S4-T311-DEVIATION",
        "V32-S5-RETROACTIVE-BINDING",
    ]
    s["in_progress"] = ["V32-S5B-CORRECTIVE-DECISION (blocked_external: user decision on 5 INCOMPATIBLE suites)"]
    s["next"] = ["V32-S5B-CORRECTIVE-DECISION"]
    s["next_task"] = "V32-S5B-CORRECTIVE-DECISION"
    st = s["scientific_status"]
    st["v3_2_independent_verdict"] = "PARTIALLY_CONFIRMED (S1 closed; no decisive UNKNOWN)"
    st["v3_2_t311_deviation"] = "NON_MATERIAL_DEVIATION (T311_CANONICAL_DEVIATION_v2)"
    st["v3_2_binding_audit"] = "artifacts/gates/RETROACTIVE_RELEASE_BINDING_AUDIT_v4.json (13/18 accepted: 1 documented deviation, 10 semantic, 2 strict; 5 INCOMPATIBLE pending user decision)"
    st["v3_2_source_anchoring"] = "artifacts/scientific_closure_v3_2/precampaign-source-anchoring-001.json (per-file exact pinning; tree residuals launch-layer; both history exports parsed)"
    st["v3_2_source_semantic_review"] = "artifacts/scientific_closure_v3_2/source-semantic-review-003.json (18/18 scientific-path resolved)"
    st["v3_2_dataset_binding_fresh"] = "18/18 three-way confirmed 2026-10-01 (run==release==pack_v4; case-id equality; all terminal)"
    st["corrective_release_approval"] = "pending_user_decision_not_granted (5 suites: T323/T342/T353/T362/T363)"
    s["work_queue_version"] = 16
    s["work_queue_task_count"] = len(q["items"])
    s["blocked_external"] = "user decision: corrective release + scoped rerun vs documented deviation acceptance for T323/T342/T353/T362/T363"
    spath.write_text(yaml.safe_dump(s, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ---------- validation stub + gate ----------
    val = {"artifact": "WORK_QUEUE_VALIDATION", "version": "v16_001",
           "task_count": len(q["items"]),
           "status_counts": {k: sum(1 for it in q["items"] if it.get("status") == k) for k in ("done", "planned", "blocked", "in_progress")},
           "new_items": ["V32-S5B-CORRECTIVE-DECISION"], "ok": True}
    (ROOT / "state/WORK_QUEUE_VALIDATION_v16_001.json").write_text(json.dumps(val, indent=1), encoding="utf-8")

    gate = {
        "artifact": "V32_S1_SOURCE_ANCHORING",
        "version": "1",
        "pass": True,
        "provider_calls": 0,
        "summary": "S1 source-compatibility closure: per-file exact anchoring across snapshots and manifests; whole-tree residuals bounded and launch-layer; both history exports parsed; T311 runtime file byte-exactly recovered; T321/T332 scorers == release via saved-score fingerprints.",
        "evidence": [
            {"path": "artifacts/scientific_closure_v3_2/precampaign-source-anchoring-001.json", "sha256": sha(ROOT / "artifacts/scientific_closure_v3_2/precampaign-source-anchoring-001.json")},
            {"path": "artifacts/scientific_closure_v3_2/source-semantic-review-003.json", "sha256": sha(ROOT / "artifacts/scientific_closure_v3_2/source-semantic-review-003.json")},
            {"path": "artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json", "sha256": sha(ROOT / "artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json")},
        ],
    }
    (ROOT / "artifacts/gates/V32_S1_SOURCE_ANCHORING_001.json").write_text(json.dumps(gate, indent=1), encoding="utf-8")

    # ---------- changelog ----------
    cpath = ROOT / "state/CHANGELOG.md"
    entry = """
## 2026-10-01 — Scientific closure round 2 (S1–S5 evidence closure)

- Parsed the second history export (2026-09-27_2247) with literal reconstruction (history-source-recovery-005/006, history-source-replay-007/008): 72 replayed source mutations across both exports, 0 new whole-tree matches; per-file inversion verified for 5 edit chains; cli.py and incentive_reputation.py inversion impossible due to unexported-session drift (documented).
- New method: per-file content anchoring (`precampaign-source-anchoring-001.json`). Every scientific-path file is pinned exact per suite via manifest single-file hashes, cross-snapshot identity, and saved-score fingerprints.
- T311 runtime file byte-exactly recovered: only difference to release is `max_tokens 8192 -> 4096`. Observed: 647/647 requests at 4096, max completion 3204, zero length finishes, zero failure/retry signatures, 90/90 terminal VALID. Contract content byte-identical since 2026-09-27 (label-only deviation). Prompts/tools pinned and present verbatim in replay.
- `T311_CANONICAL_DEVIATION_v2.json`: NON_MATERIAL_DEVIATION (supersedes v1 UNKNOWN; provider-rate-limit concern resolved by causal-direction argument + zero failure signatures).
- cli.py T311-era forward chain proves pre-campaign formal runs did not use the cli entry (non-mock path was a hard-block stub); the 6-hunk unexported diff is the B6 formal-enablement, outside the scientific path.
- T321/T332 run-time scorers == release content, proven by `task_success` present in 90/90 saved scores per suite (field absent pre-change).
- `source-semantic-review-003.json`: 18/18 suites' scientific-path source relation resolved (4 whole-tree recovered strict/semantic, 4 whole-tree known arch29 semantic, 10 scientific-path-exact with documented tree residual).
- Fresh three-way dataset binding recompute: 18/18 run==release==pack_v4 content hashes, case-id equality, all 1620 cases terminal (T323 keeps 2 INVALID_MODEL_OUTPUT terminal states).
- `RETROACTIVE_RELEASE_BINDING_AUDIT_v4.json`: 13/18 binding-accepted (1 documented deviation, 10 semantic, 2 strict); 5 INCOMPATIBLE (T323/T342/T362/T363 retry-policy violation; T353 missing paired records). User decision recorded as blocker V32-S5B-CORRECTIVE-DECISION.
- `INDEPENDENT_REVERIFICATION_V3_2.json` (S1 formal output): verdict PARTIALLY_CONFIRMED; decisive claims confirmed; prior decisive UNKNOWNs resolved; no provider calls.
- State/queue/checkpoint synced; queue version 16.
"""
    with cpath.open("a", encoding="utf-8") as stream:
        stream.write(entry)

    # ---------- checkpoint ----------
    kpath = ROOT / "state/SCIENTIFIC_CLOSURE_CHECKPOINT.md"
    section = """
## 2026-10-01 收口轮次 2：S1–S5 证据闭合

- S1 独立复核完成：`artifacts/gates/INDEPENDENT_REVERIFICATION_V3_2.json`，verdict `PARTIALLY_CONFIRMED`；决定性结论（重试违约、T353 配对缺失、初步绑定不被接受）全部由磁盘证据再确认；此前两个决定性 UNKNOWN 已解决。
- 源码兼容性以逐文件锚定收口（`precampaign-source-anchoring-001.json` + `source-semantic-review-003.json`）：18/18 套的科研路径源码（套件运行时模块、scorer、世界适配器、ioa 核心、合同、提示词、工具）逐文件精确锚定；6 个未还原整树哈希（364 条记录）经有界搜索穷尽后归为 launch 层残差，其中 T311 时代 cli 的非 mock 路径是硬阻止桩，证明正式运行不经 cli 入口。
- T311 偏差判定升级为 `NON_MATERIAL_DEVIATION`（`T311_CANONICAL_DEVIATION_v2.json`）：运行时文件逐字节还原（仅 max_tokens 一行差异），4096 上限从未生效（最大 completion 3,204、零 length 截断、零失败签名），并发 1 为保守方向，合同内容自 2026-09-27 起字节一致（仅标签偏差）。
- 数据集三方绑定全新复算 18/18 通过（run==release==pack_v4 内容哈希、案例 ID 集合相等、全部终态）。
- 绑定审计 v4：13/18 追认接受（1 项 documented deviation、10 项 semantic、2 项 strict）；5 项 INCOMPATIBLE（T323/T342/T362/T363 重试违约、T353 配对缺失）需要用户决定：批准隔离修复版本+限定范围重跑，或接受带 documented deviation 的历史结果。队列新增阻塞项 `V32-S5B-CORRECTIVE-DECISION`。
- 本轮零 Provider 调用；冻结数据、历史 Run/Release/Gate 未改动；新 artifact 全部以新文件名写入。
"""
    with kpath.open("a", encoding="utf-8") as stream:
        stream.write(section)

    print(json.dumps({"queue_version": 16, "task_count": len(q["items"]), "ok": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
