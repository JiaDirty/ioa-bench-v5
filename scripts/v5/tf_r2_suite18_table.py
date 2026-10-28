"""Regenerate the 18-suite capability reuse table for R2 (read-only synthesis).

Adds the R2 business-binding status per suite: which suites have typed
compilers, which consume BusinessBinding today, and the remaining capability
gaps. T322's VERSION_SCOPED 5.1.0 gap (120 historical cases) stays recorded.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"

from ioabench.v5.ai_generation.compiler_capabilities import PILOT_FACTORS  # noqa: E402
from ioabench.v5.ai_generation.business_binding import BUSINESS_FLOW  # noqa: E402
from ioabench.v5.ai_generation.bounded_compiler import FACTORS  # noqa: E402

NAMES = {"T311": "资格伪装", "T312": "注册失真", "T313": "代表资格漂移",
         "T321": "协商污染", "T322": "互操作失配", "T323": "责任链断裂",
         "T331": "跨系统级联扩散", "T332": "结构暴露", "T333": "行为推断",
         "T341": "生态错误共识", "T342": "谣言扩散", "T343": "规范漂移",
         "T351": "激励错配", "T352": "声誉垄断", "T353": "节点操纵",
         "T361": "判断让渡", "T362": "讨论扭曲", "T363": "能动性弱化"}


def main() -> int:
    rows = []
    for suite, name in NAMES.items():
        typed = suite in {"T312", "T321", "T331", "T352", "T362"}
        binding_now = suite in {"T321", "T331", "T362"}
        rows.append({
            "suite": suite, "name": name,
            "typed_compiler": "yes" if typed else "bounded_grammar",
            "business_binding_consumed": "yes (R2)" if binding_now else "not yet",
            "pilot_factors_registered": len(PILOT_FACTORS.get(suite, ())),
            "bounded_factor_primitives": 1 if f"{suite}-DYNA" in FACTORS else 0,
            "r2_accepted_this_round": "see INSTANCE_YIELD.csv",
            "reusable_r2_primitives": "BusinessBinding.compile + business_tools duty layer + "
                                      "witness prelude + IR fail-closed projection",
            "remaining_capability_gap": "bind suite-specific business flow + slice duty tools"
                                        if not binding_now else "none for the pilot scope",
            "known_scope_limits": "T322 VERSION_SCOPED 5.1.0 historical 120-case gap retained; "
                                  "T361-T363 SIMULATION_ONLY" if suite in {"T322", "T361", "T362", "T363"}
                                 else "additive world keys keep oracle/scorer unchanged",
            "priority": "P0 (pilot, binding live)" if binding_now else "P1/P2 (adapter reuse)"})
    with (RUN / "SUITE18_CAPABILITY_READINESS_R2.csv").open("w", encoding="utf-8",
                                                            newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
