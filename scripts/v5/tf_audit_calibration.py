"""M1 offline audit-contract calibration evidence (zero provider calls).

Reuses the v1.2 contract builders from tests/v5/test_tf_audit_facts.py so the
evidence and the regression suite exercise exactly the same code path. The live
same-model two-effort verdict dimension is measured during the M5 A/B pilot; this
report covers the deterministic contract layer only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1/AUDIT_CALIBRATION.json"


def load_test_module():
    spec = importlib.util.spec_from_file_location(
        "tf_audit_facts_test", ROOT / "tests/v5/test_tf_audit_facts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    test = load_test_module()
    rows, summary = [], {"planned_negatives": 0, "hard_gate_intercepted": 0,
                         "fact_blocked": 0, "false_accepts": 0, "planned_positives": 0,
                         "accepted": 0, "false_rejects": 0, "provider_calls": 0}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Positives: six truthful accepts across T331/T321/T362.
        for suite, target in test.POSITIVE_CASES:
            source, _ = test.build_source(tmp, suite, target)
            packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
            study = test.Study12(tmp, packet["audit_facts"])
            result = asyncio_run(test.audit_packet(study, packet, tmp / f"pos-{len(rows)}"))
            accepted = result["status"] == "DEV_AUTO_AUDITED"
            rows.append({"kind": "positive", "suite": suite, "target": target,
                         "status": result["status"], "accepted": accepted,
                         "false_reject": not accepted,
                         "validation_errors": [row["validation_errors"] for row in result["reviews"]]})
            summary["planned_positives"] += 1
            summary["accepted"] += int(accepted)
            summary["false_rejects"] += int(not accepted)
        # New negatives: document-level mutations with an ACCEPT-forming review.
        mutations = {
            "MULTIPLE_INTERVENTIONS": ("T331", lambda d: d["cases"][0]["scenario_world"].update(rogue_extra_field="x")),
            "NO_CAUSAL_EFFECT": ("T331", lambda d: d["cases"][1].update(scenario_world=d["cases"][0]["scenario_world"])),
            "UNPAIRED": ("T331", lambda d: d.update(cases=d["cases"][:1])),
            "ORACLE_LEAKAGE_V12": ("T331", lambda d: (
                d["cases"][0]["oracle_hidden"].update(secret_marker="HIDDEN_TRUTH_SENTINEL_9c2b"),
                d["execution"]["sut_visible"]["messages"].append(
                    {"arm": "CONTROL", "message": {"role": "user", "content": "Reminder: HIDDEN_TRUTH_SENTINEL_9c2b"}}))),
            "REPLAY_MISMATCH_V12": ("T331", lambda d: d["replay"][0]["checks"].update(events=False)),
            "HISTORY_DUPLICATE_V12": ("T331", lambda d: d["history"][0]["full_comparison_statistics"].update(exact_duplicate_count=1)),
            "ACTION_OBSERVATION_EVIDENCE_CONTRADICTION": ("T331", lambda d: d["execution"]["tool_observation_consistency"][0].update(
                mismatches=["tool observation mismatch at action 0"])),
        }
        for name, (suite, mutate) in mutations.items():
            source, _ = test.build_source(tmp, suite)
            packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
            documents = json.loads(json.dumps(packet["documents"]))
            mutate(documents)
            mutated = dict(packet, documents=documents,
                           audit_facts=test.facts_from_documents(documents, base=packet["audit_facts"]))
            study = test.Study12(tmp, mutated["audit_facts"])
            result = asyncio_run(test.audit_packet(study, mutated, tmp / f"neg-{name}"))
            blocked = result["status"] == "QUARANTINED"
            rows.append({"kind": "negative_new", "name": name, "suite": suite,
                         "status": result["status"], "blocked": blocked, "false_accept": not blocked,
                         "hard_gate_intercepted": bool(result["hard_gate_errors"]),
                         "fact_blocked": any(code.startswith(("UNPAIRED", "MULTIPLE", "NO_CAUSAL",
                             "ORACLE", "REPLAY", "HISTORY", "ACTION", "DESIGN"))
                             for row in result["reviews"] for code in row["validation_errors"])})
            summary["planned_negatives"] += 1
            summary["hard_gate_intercepted"] += int(rows[-1]["hard_gate_intercepted"])
            summary["fact_blocked"] += int(rows[-1]["fact_blocked"])
            summary["false_accepts"] += int(not blocked)
        # Review-contract negatives on an honest packet (the reviewer is the defect).
        source, _ = test.build_source(tmp, "T331")
        packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
        contract_faults = {
            "CLAIM_FACT_CONTRADICTION": test.Study12(tmp, packet["audit_facts"],
                                                     overrides={"replay_rows": 99}),
            "FACT_COVERAGE_INCOMPLETE": test.Study12(tmp, packet["audit_facts"],
                                                     drop_keys={"arms"}),
            "FACT_CLAIM_UNBOUND": test.Study12(tmp, packet["audit_facts"], unbound=True),
            "FACT_KEY_UNKNOWN": test.Study12(tmp, packet["audit_facts"], unknown_key=True),
            "AUDIT_FORMAT_INVALID": test.Study12(tmp, packet["audit_facts"], mode="raw-json"),
        }
        for name, study in contract_faults.items():
            result = asyncio_run(test.audit_packet(study, packet, tmp / f"fault-{name}"))
            blocked = result["status"] == "QUARANTINED"
            rows.append({"kind": "negative_review_fault", "name": name, "status": result["status"],
                         "blocked": blocked, "false_accept": not blocked,
                         "fact_blocked": any(code.startswith(("CLAIM_FACT", "FACT_", "AUDIT_FORMAT"))
                                             for row in result["reviews"]
                                             for code in row["validation_errors"])})
            summary["planned_negatives"] += 1
            summary["fact_blocked"] += int(rows[-1]["fact_blocked"])
            summary["false_accepts"] += int(not blocked)
        # The frozen six historical negatives re-checked on v1.2 facts.
        frozen_base = ROOT / test.FROZEN_CALIBRATION
        for case in range(1, 7):
            frozen = frozen_base / f"case-{case}" / "AUDIT_PACKET.json"
            if not frozen.is_file():
                continue
            packet = json.loads(frozen.read_text(encoding="utf-8"))
            facts = test.facts_from_documents(packet["documents"])
            errors = test.assertion_evidence_consistency(
                {"verdict": "ACCEPT", "fact_claims": [
                    {"fact_key": key, "value": value, "evidence_file": "inputs/execution.json",
                     "json_pointer": ""} for key, value in facts.items() if key != "version"]}, facts)
            fact_blocked = any(code.split(":")[0] in {
                "UNPAIRED", "MULTIPLE_INTERVENTIONS", "NO_CAUSAL_EFFECT", "ORACLE_LEAKAGE",
                "HISTORY_DUPLICATE", "REPLAY_MISMATCH", "ACTION_OBSERVATION_EVIDENCE_CONTRADICTION",
                "DESIGN_NOT_CONSUMED"} for code in errors)
            rows.append({"kind": "negative_frozen", "case": case,
                         "mutation": (packet["hard_gate_errors"] or [None])[0],
                         "fact_blocked": fact_blocked,
                         "hard_gate_intercepted": bool(packet["hard_gate_errors"]),
                         "false_accept": not fact_blocked and not packet["hard_gate_errors"]})
            summary["planned_negatives"] += 1
            summary["hard_gate_intercepted"] += int(rows[-1]["hard_gate_intercepted"])
            summary["fact_blocked"] += int(fact_blocked)
            summary["false_accepts"] += int(rows[-1]["false_accept"])
    report = {"version": "ioabench.v5.audit-contract-calibration/2.0.0",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "protocol": test.PROTOCOL_V12, "provider_calls": 0,
              "summary": summary, "rows": rows,
              "live_same_model_two_effort_verdicts": "NOT_RUN_THIS_MILESTONE_MEASURED_IN_AB_PILOT",
              "scientific_independent_validation": False}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if summary["false_accepts"] == 0 and summary["false_rejects"] == 0 else 1


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


if __name__ == "__main__":
    raise SystemExit(main())
