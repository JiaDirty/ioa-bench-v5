"""R2 M2 offline audit-contract calibration: 12+ UNSEEN negatives, 6 positives.

Zero provider calls (scripted Study12 reviewers). Distinct from the R1
calibration (18 negatives/6 positives retained read-only in tf-20261024-r1):
every mutation below is new — reviewer-fact contradictions, pointer/hash
spoofing, cross-suite packets, business-binding arm deltas, tool-channel
oracle leakage, near-duplicate history and unwitnessed design claims.
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

OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1/AUDIT_CALIBRATION_R2.json"


def load_test_module():
    spec = importlib.util.spec_from_file_location(
        "tf_audit_facts_test", ROOT / "tests/v5/test_tf_audit_facts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(test, study, packet, out, *, reviewer=None):
    import asyncio
    return asyncio.run(test.audit_packet(study, packet, out))


def main() -> int:
    test = load_test_module()
    rows, summary = [], {"planned_negatives": 0, "blocked": 0, "false_accepts": 0,
                         "planned_positives": 0, "accepted": 0, "false_rejects": 0,
                         "provider_calls": 0}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # ---- six valid positives on the unchanged v1.2 contract --------------
        for suite, target in test.POSITIVE_CASES:
            source, _ = test.build_source(tmp, suite, target)
            packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
            study = test.Study12(tmp, packet["audit_facts"])
            result = run(test, study, packet, tmp / f"pos-{len(rows)}")
            accepted = result["status"] == "DEV_AUTO_AUDITED"
            rows.append({"kind": "positive", "suite": suite,
                         "target": target or {}, "status": result["status"],
                         "accepted": accepted, "false_reject": not accepted})
            summary["planned_positives"] += 1
            summary["accepted"] += int(accepted)
            summary["false_rejects"] += int(not accepted)

        # ---- 12+ unseen negatives -------------------------------------------
        # (a0) a registered design assertion that execution never witnessed: the
        # source carries an unwitnessed ASSERTION_WITNESSES row before sealing
        source, _ = test.build_source(tmp, "T331")
        (source / "ASSERTION_WITNESSES.jsonl").write_text(json.dumps({
            "assertion_id": "T331-A1", "verified": False,
            "status": "DESIGN_EXECUTION_FIDELITY_FAIL",
            "predicate": "rebroadcast lands only after the propagation wave"}) + "\n",
            encoding="utf-8")
        packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
        study = test.Study12(tmp, packet["audit_facts"])
        result = run(test, study, packet, tmp / "neg-R2_UNWITNESSED_DESIGN_CLAIM")
        blocked = result["status"] == "QUARANTINED"
        rows.append({"kind": "negative_document", "name": "R2_UNWITNESSED_DESIGN_CLAIM",
                     "status": result["status"], "blocked": blocked,
                     "false_accept": not blocked,
                     "review_errors": [row["validation_errors"] for row in result["reviews"]]})
        summary["planned_negatives"] += 1
        summary["blocked"] += int(blocked)
        summary["false_accepts"] += int(not blocked)

        # (a) document-level forgeries the program facts must expose
        doc_mutations = {
            "R2_SINGLE_ARM_EXECUTION": lambda d: d.update(
                execution={**d["execution"], "runs": [row for row in d["execution"]["runs"]
                                                      if row.get("arm") == "RISK"]}),
            "R2_CROSS_SUITE_CASE": lambda d: d["cases"][1]["metadata"].update(suite_id="T313"),
            "R2_BINDING_ARM_DELTA": lambda d: d["cases"][1]["scenario_world"].setdefault(
                "business_binding", {}).update(root="industry.payment_clearing"),
            "R2_ORACLE_LEAK_IN_TOOLS": lambda d: (
                d["cases"][0]["oracle_hidden"].update(secret_marker="HIDDEN_TRUTH_SENTINEL_9c2b"),
                d["execution"]["sut_visible"].setdefault("tools", []).append(
                    {"function": {"name": "HIDDEN_TRUTH_SENTINEL_9c2b"}})),
            "R2_NEAR_DUPLICATE_HISTORY": lambda d: d["history"][0][
                "full_comparison_statistics"].update(no_dimension_near_duplicate_count=3),
            "R2_EMPTY_REFERENCE_ACTIONS": lambda d: [run.setdefault("actions", []).clear()
                                                     for run in d["execution"]["runs"]],
        }
        for name, mutate in doc_mutations.items():
            source, _ = test.build_source(tmp, "T331")
            packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
            documents = json.loads(json.dumps(packet["documents"]))
            mutate(documents)
            mutated = dict(packet, documents=documents,
                           audit_facts=test.facts_from_documents(documents, base=packet["audit_facts"]))
            study = test.Study12(tmp, mutated["audit_facts"])
            result = run(test, study, mutated, tmp / f"neg-{name}")
            blocked = result["status"] == "QUARANTINED"
            rows.append({"kind": "negative_document", "name": name,
                         "status": result["status"], "blocked": blocked,
                         "false_accept": not blocked,
                         "review_errors": [row["validation_errors"] for row in result["reviews"]]})
            summary["planned_negatives"] += 1
            summary["blocked"] += int(blocked)
            summary["false_accepts"] += int(not blocked)

        # (b) reviewer-side forgeries: truthful packet, dishonest review
        source, _ = test.build_source(tmp, "T331")
        packet = test.prepare_audit_packet(source, protocol=test.PROTOCOL_V12)
        facts = packet["audit_facts"]
        review_faults = {
            "R2_FACT_VALUE_WRONG_TYPE": test.Study12(tmp, facts, overrides={"replay_rows": "seven"}),
            "R2_FACT_OVERRIDE_WORLD_DELTA": test.Study12(
                tmp, facts, overrides={"world_delta_paths": ["/suite_payload/organization"]}),
            "R2_FACT_FABRICATES_LEAKAGE": test.Study12(
                tmp, facts, overrides={"oracle_leakage_present": True}),
            "R2_FACT_OVERRIDE_REPLAY_FAILED": test.Study12(
                tmp, facts, overrides={"replay_all_passed": False}),
            "R2_EVIDENCE_HASH_SPOOF": test.Study12(tmp, facts),
            "R2_UNWITNESSED_ASSERTION_OVERRIDE": test.Study12(
                tmp, facts, overrides={"design_assertions_verified": True}),
        }
        for name, study in review_faults.items():
            if name == "R2_EVIDENCE_HASH_SPOOF":
                # same truthful review, but every evidence hash is wrong
                original = study._review

                def spoof(messages):
                    review = json.loads(original(messages))
                    for ref in review["evidence_refs"]:
                        ref["sha256"] = "0" * 64
                    return json.dumps(review)
                study._review = spoof
            if name == "R2_UNWITNESSED_ASSERTION_OVERRIDE":
                # facts genuinely carry an unwitnessed assertion row; the review
                # claims verified=true anyway -> contradiction
                documents = json.loads(json.dumps(packet["documents"]))
                packet = dict(packet, documents=documents,
                              audit_facts=test.facts_from_documents(
                                  documents, base=packet["audit_facts"]))
                packet["audit_facts"]["design_assertions_verified"] = False
                study.facts = packet["audit_facts"]
            result = run(test, study, packet, tmp / f"fault-{name}")
            blocked = result["status"] == "QUARANTINED"
            rows.append({"kind": "negative_review_fault", "name": name,
                         "status": result["status"], "blocked": blocked,
                         "false_accept": not blocked,
                         "review_errors": [row["validation_errors"] for row in result["reviews"]]})
            summary["planned_negatives"] += 1
            summary["blocked"] += int(blocked)
            summary["false_accepts"] += int(not blocked)

    report = {"version": "ioabench.v5.audit-contract-calibration-r2/1.0.0",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "protocol": test.PROTOCOL_V12, "provider_calls": 0,
              "summary": summary, "rows": rows,
              "relation_to_r1": "R1 18-negative/6-positive calibration retained "
                                "read-only at artifacts/v5/tree_factory/tf-20261024-r1/"
                                "AUDIT_CALIBRATION.json; all mutations here are unseen",
              "live_same_model_two_effort_verdicts": "measured during R2 online pilots",
              "scientific_independent_validation": False}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    ok = summary["false_accepts"] == 0 and summary["false_rejects"] == 0 \
        and summary["planned_negatives"] >= 12 and summary["planned_positives"] >= 6
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
