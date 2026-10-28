"""R3 suite capability inventory (doc 09): four-level status for all 18 suites.

The compositional business-DAG layer exposes this honest per-suite capability
answer: pilots are actually exercised end-to-end; the other 15 suites report
their true status instead of inheriting the pilots' path implicitly.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone as tz
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"

SUITES = [f"T3{minor}{index}" for minor, count in ((1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3))
          for index in range(1, count + 1)]
PILOTS = {"T321", "T331", "T362"}


def suite_workflow_capabilities(suite: str) -> dict:
    canonical = suite.split("-")[0]
    if canonical in PILOTS:
        return {
            "suite": canonical,
            "catalog_ready": True,
            "catalog_detail": "both industries; 8 modules each incl fork/join/conditional/attest",
            "compiler_ready": True,
            "compiler_detail": "workflow_compiler.compile_plan -> BusinessBinding.from_plan -> "
                               "existing suite compilers via blueprint_from_ir",
            "runtime_witnessed": True,
            "runtime_detail": "real engine episodes; receipt-chain witnesses WITNESSED "
                              "(tests + T321 proof; T331/T362 full-chain tests)",
            "dev_pool_verified": "PENDING_ONLINE (gateway outage)",
            "tested_actor_model": "suite-fixed single/multi agent layouts preserved",
            "risk_slot_discipline": "CONTROL/RISK differ only in the pre-existing mechanism slot",
            "oracle_invariants": "unchanged; business layer carries no truth",
            "workflow_schema_version": "ioabench.v5.workflow-plan/1.0.0",
            "unsupported": []}
    return {
        "suite": canonical,
        "catalog_ready": "SHARED_CATALOG_AVAILABLE",
        "catalog_detail": "the module catalog is suite-agnostic, but no suite-specific "
                          "consumption exists for this suite",
        "compiler_ready": False,
        "compiler_detail": "no adapter integration: this suite's compiler does not consume "
                           "business_binding in its suite_payload schema",
        "runtime_witnessed": False,
        "dev_pool_verified": False,
        "status": "UNSUPPORTED_WITH_REASON",
        "reason": "R3 scope is the three pilots; extending to this suite requires (a) a "
                  "business_binding property in its generator schema, (b) slice-level "
                  "business_grants/business_tools integration, (c) delivery-fidelity "
                  "accounting if cross-agent joins are used",
        "workflow_schema_version": "ioabench.v5.workflow-plan/1.0.0"}


def main() -> None:
    rows = [suite_workflow_capabilities(suite) for suite in SUITES]
    report = {"version": "ioabench.v5.r3.suite-capabilities/1.0.0",
              "generated_at_utc": datetime.now(tz.utc).isoformat(),
              "policy": "honest per-suite status; pilots never imply the other 15",
              "second_layer_recommendation": "one suite with a distinct participant/tool "
                                             "profile (T352 reputation/governance or T332 "
                                             "alternate cascade) next, per doc 09",
              "suites": rows}
    (OUT / "SUITE_CAPABILITIES_R3.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"total": len(rows),
                      "pilots": sum(r.get("compiler_ready") is True for r in rows),
                      "unsupported_with_reason": sum(r.get("status") == "UNSUPPORTED_WITH_REASON"
                                                     for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
