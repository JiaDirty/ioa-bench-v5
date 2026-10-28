"""Emit SUITE18_CAPABILITY_READINESS.csv from the live compiler registry (offline)."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"

from ioabench.v5.ai_generation.bounded_compiler import FACTORS
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.core.case import SUITES

NAMES = {"T311": "资格伪装", "T312": "注册失真", "T313": "代表资格漂移", "T321": "协商污染",
         "T322": "互操作失配", "T323": "责任链断裂", "T331": "跨系统级联扩散", "T332": "结构暴露",
         "T333": "行为推断", "T341": "生态错误共识", "T342": "谣言扩散", "T343": "规范漂移",
         "T351": "激励错配", "T352": "声誉垄断", "T353": "节点操纵", "T361": "判断让渡",
         "T362": "讨论扭曲", "T363": "能动性弱化"}
TYPED = {"T312", "T321", "T331", "T352", "T362"}
PILOT = {"T331", "T321", "T362"}
IR_PRIMITIVES = {
    "T331": "typed topology lattice + rebroadcast_timing + confirmation_loop (本轮)",
    "T321": "broker/profile/offer_access + close_gate + renegotiation_window (本轮)",
    "T362": "evidence graph/release + source_release + relay_before_digest (本轮)",
    "T312": "registry projection primitives; reuse delayed-evidence-release pattern",
    "T313": "chain projection; reuse staged-release timing pattern",
    "T322": "native record access; keep VERSION_SCOPED until 5.1.0 sources recovered",
    "T323": "reconstruction delivery; reuse after_turn install hook pattern",
    "T332": "directory projection; reuse visibility-window pattern",
    "T333": "metadata access; reuse query-gated release pattern",
    "T341": "recirculation access; reuse broadcast/committee_query split",
    "T342": "register access; reuse per-role permission lattice pattern",
    "T343": "activity feed; reuse push/handbook_query split",
    "T351": "screening publication; reuse queued-history-reply timing",
    "T352": "typed provider registry + receipt alignment (2-unit history)",
    "T353": "catalogue evidence; reuse quote-on-request gating",
    "T361": "item release; SIMULATION_ONLY persona path",
    "T363": "task release flip; SIMULATION_ONLY persona path",
}
HOOKS = {
    "T331": "none further (this round added after_turn timing + ack collection)",
    "T321": "none further (close gate + renegotiation window landed)",
    "T362": "none further (per-owner release + relay gate landed)",
    "T312": "after_turn registry amendment hook for a second projection axis",
    "T313": "delegation-depth gate on dispatch/read_subgrant",
    "T322": "gateway mapping receipt consumer + original 5.1.0 source recovery (external)",
    "T323": "reconstruction completeness check before delivery",
    "T332": "second projection axis (partial redaction) in open_record",
    "T333": "second metadata class with distinct visibility",
    "T341": "committee composition variation hook",
    "T342": "hop-cap variation on the register permission",
    "T343": "feed retention window hook",
    "T351": "screening timing axis (delayed push) hook",
    "T353": "quote provenance axis hook",
    "T351x": "",
    "T361": "paired_after_first variation already present; needs measured calibration only",
    "T363": "flip position axis hook",
}
RISK = {
    "T322": "HIGH: 120 unprojectable 5.1.0 records; any new claim stays VERSION_SCOPED",
    "T361": "MEDIUM: persona-only construct; SIMULATION_ONLY constraints",
    "T363": "MEDIUM: persona-only construct; SIMULATION_ONLY constraints",
    "T352": "MEDIUM: legacy receipt pollution quarantines; new units must not relabel them",
}
rows = []
for suite in SUITES:
    canonical = suite[:4]
    factors = FACTORS.get(suite + "-DYNA", FACTORS.get(f"{canonical}-DYNA"))
    factor_count = len(factors[1]) if factors else (5 if canonical == "T331" else
                                                    5 if canonical == "T321" else
                                                    5 if canonical == "T362" else 1)
    row = {"suite": canonical, "name": NAMES[canonical],
           "typed_compiler": "yes" if canonical in TYPED else "bounded_grammar",
           "pilot_this_round": "yes" if canonical in PILOT else "no",
           "consumed_factors_current": factor_count,
           "new_factors_this_round": {"T331": "rebroadcast_timing, confirmation_loop",
                                      "T321": "close_gate, renegotiation_window",
                                      "T362": "source_release, relay_before_digest"}.get(canonical, ""),
           "reusable_ir_primitives": IR_PRIMITIVES.get(canonical, ""),
           "new_runtime_hooks_needed": HOOKS.get(canonical, "one gated hook per new factor"),
           "oracle_scorer_conflict_risk": RISK.get(canonical, "low: additive world keys keep oracle/scorer unchanged"),
           "priority": {"T331": "P0 (pilot done)", "T321": "P0 (pilot done)", "T362": "P0 (pilot done)",
                        "T352": "P1 (typed compiler exists)", "T312": "P1",
                        "T322": "P2 (external source recovery first)"}.get(canonical, "P2")}
    rows.append(row)
with (OUT / "SUITE18_CAPABILITY_READINESS.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(json.dumps({"rows": len(rows)}, ensure_ascii=False))
