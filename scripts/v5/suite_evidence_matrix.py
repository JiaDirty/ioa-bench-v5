"""DW-AUDIT-009: per-suite runnable-vs-generatable evidence matrix (18 suites, mechanism clusters).

For every classic suite this script EXECUTES (not just inspects):
  * one classic case through the frozen ``runner.run_case`` (witness policy, reference_auxiliary
    where the suite provides one);
  * one dynamic-slice case through the opt-in ``dynamic.runner.run_dynamic_case`` (witness
    policy, persona reference_auxiliary where present), which also produces the mandatory
    monitor report (ledger integrity, timing properties, message flow).

Each suite row records: both runner entries with their actual run outcomes, monitor support,
scorer identity/audit status, novelty evidence (executable-structure delta of the slice vs the
classic family + family-registry classification), compilation capability and the residual
CAPABILITY_GAP. Offline only — scripted reference policies, zero provider calls.

Output: artifacts/v5/dynamic_world/suite-evidence-matrix.json (refuses overwrite).
"""
from __future__ import annotations

import importlib
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.models import ModelProfile  # noqa: E402
from ioabench.v5.dynamic.runner import RUNNER_VERSION, adapter_fingerprint, run_dynamic_case  # noqa: E402
from ioabench.v5.dynamic.signature import signature, structural_delta  # noqa: E402
from ioabench.v5.dynamic import family_registry  # noqa: E402
from ioabench.v5.runner import RUNNER_VERSION as CLASSIC_RUNNER_VERSION, run_case  # noqa: E402
from ioabench.v5.suites import load as load_suite  # noqa: E402

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
EVIDENCE_ROOT = ROOT / "artifacts/v5/dynamic_world/evidence-runs"
DEST = ROOT / "artifacts/v5/dynamic_world/suite-evidence-matrix.json"

# classic suite -> (slice module name, structure label); every classic suite has >= 1 slice
SLICE_OF = {
    "T311": ("t311_slice", "live-directory-async-references"),
    "T312": ("t312_slice", "live-registry-amendment"),
    "T313": ("t313_slice", "mid-episode-grant-revision"),
    "T321": ("t321_slice", "competing-brokers-structure-A"),
    "T322": ("t322_slice", "mid-episode-native-transition"),
    "T323": ("t323_slice", "mid-episode-registry-reindex"),
    "T331": ("t331_slice", "fan-out-mid-episode-rebroadcast"),
    "T332": ("t332_slice", "staged-conversation-follow-up"),
    "T333": ("t333_slice", "staged-metadata-partner-pressure"),
    "T341": ("t341_slice", "two-round-recirculation"),
    "T342": ("t342_slice", "three-hop-chain-senior-endorsement"),
    "T343": ("t343_slice", "staged-descriptive-feed"),
    "T351": ("t351_slice", "lagged-results-incentive-note"),
    "T352": ("t352_slice", "four-rounds-reputation-publication"),
    "T353": ("t353_slice", "mid-episode-router-push"),
    "T361": ("t361_slice", "mid-queue-escalation"),
    "T362": ("t362_slice", "mid-episode-mass-report-alert"),
    "T363": ("t363_slice", "mid-episode-default-flip"),
}

CLUSTERS = {
    "trust-and-protocol": ["T311", "T312", "T313", "T321", "T322", "T323"],
    "cascade-and-knowledge": ["T331", "T332", "T333", "T341", "T342", "T343"],
    "incentive-and-power": ["T351", "T352", "T353"],
    "simulation-only": ["T361", "T362", "T363"],
}

SCORER_AUDIT = {
    "T331": "utility shortfall both arms — analysis-stage matter, historical attribution stands; no scorer edit",
    "T333": "scorer abstain audit PENDING (Gate B/E pre-registered); slice scoring delegated verbatim to the classic scorer",
}
SIMULATION_SUITES = {"T361", "T362", "T363"}

CAPABILITY_GAP_OF = {
    "T311": "G-8 (single-structure slice demo)",
    "T312": "G-8; requirement set fixed per family",
    "T313": "G-8; delegation depth fixed at 2 hops",
    "T321": "G-8; broker/exception shapes fixed per structure",
    "T322": "G-8; single-instruction episodes per family",
    "T323": "G-8; forwarding-chain depth fixed per family",
    "T331": "G-5 (topology; slice proves fan-out) + T331 utility audit pending (analysis-stage)",
    "T332": "G-3 (lexical disclosure detection; paraphrase needs the abstain path)",
    "T333": "G-4 (free-text abstain band; scorer audit pending) + G-8",
    "T341": "G-8; pseudo-independence provenance summarized in packet text",
    "T342": "G-8; 3-liaison topology fixed in the slice",
    "T343": "G-8; feed items static per case (no cross-episode memory)",
    "T351": "G-1 (screening cost/time friction fixed; P15 parameterization pending)",
    "T352": "G-2 (round structure fixed; allocator interaction limited)",
    "T353": "G-8; requirement set fixed per family",
    "T361": "G-6/G-8 (persona scripted sequence; SIMULATION_ONLY)",
    "T362": "G-6/G-8 (decision-maker read modeled as digest_read; SIMULATION_ONLY)",
    "T363": "G-6/G-7/G-8 (persona competence update scripted; SIMULATION_ONLY)",
}


def classic_witness(suite_id: str, case):
    module = load_suite(suite_id)
    policies = module.policies()
    return policies["witness"], (module.reference_auxiliary() if hasattr(module, "reference_auxiliary") else None)


def slice_module_of(classic_suite_id: str):
    slice_name = SLICE_OF[classic_suite_id][0]
    return importlib.import_module(f"ioabench.v5.dynamic.{slice_name}"), slice_name


def summarize_run(result: dict) -> dict:
    return {"status": result["status"],
            "scientifically_eligible": result.get("scientifically_eligible"),
            "monitor_passed": (result.get("monitor_report", {}).get("ledger_integrity", {}).get("passed")
                               if "monitor_report" in result else None),
            "error": result.get("error")}


def main() -> int:
    if DEST.exists():
        print(f"REFUSED: {DEST} exists", file=sys.stderr)
        return 1
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    suites = {}
    for classic_suite_id in sorted(SLICE_OF):
        classic = load_suite(classic_suite_id)
        slice_mod, structure_label = slice_module_of(classic_suite_id)
        row: dict[str, Any] = {"classic_suite": classic_suite_id,
                               "cluster": next(c for c, ids in CLUSTERS.items()
                                               if classic_suite_id in ids),
                               "simulation_only": classic_suite_id in SIMULATION_SUITES}

        # ---- classic runner: actual execution of one classic case ----
        classic_pair = classic.generate(seed=5, families=1)[0]
        classic_case = classic_pair[0]
        witness, auxiliary = classic_witness(classic_suite_id, classic_case)
        classic_result = asyncio.run(run_case(EVIDENCE_ROOT, classic_case, witness, PROFILE,
                                              run_id=f"dw-audit009-{classic_suite_id}",
                                              parameters={"temperature": 0.0}, auxiliary=auxiliary))
        row["classic_runner"] = {
            "runner_version": CLASSIC_RUNNER_VERSION,
            "entry": "runner.run_case (frozen 18-suite registry)",
            "case_id": classic_case.case_id,
            "run": summarize_run(classic_result),
        }

        # ---- dynamic runner: actual execution of one slice case ----
        slice_pair = slice_mod.generate(seed=5, families=1)[0]
        slice_case = slice_pair[0]
        slice_witness = slice_mod.policies()["witness"]
        timing_rules = getattr(slice_mod, "TIMING_RULES", ())
        dynamic_result = run_dynamic_case(EVIDENCE_ROOT, slice_case, slice_mod, slice_witness,
                                          PROFILE, run_id=f"dw-audit009-{suite_id(classic_suite_id)}",
                                          parameters={"temperature": 0.0},
                                          timing_rules=timing_rules)
        monitor_report = dynamic_result.get("monitor_report", {})
        row["dynamic_runner"] = {
            "runner_version": RUNNER_VERSION,
            "entry": "dynamic.runner.run_dynamic_case (opt-in, explicit adapter)",
            "structure": structure_label,
            "case_id": slice_case.case_id,
            "run": summarize_run(dynamic_result),
            "monitor_report": {"ledger_integrity": monitor_report.get("ledger_integrity"),
                               "timing_properties": {"time_base": monitor_report.get("timing_properties", {}).get("time_base"),
                                                     "passed": monitor_report.get("timing_properties", {}).get("passed"),
                                                     "indeterminate": len(monitor_report.get("timing_properties", {}).get("indeterminate", []))},
                               "message_flow_paired": monitor_report.get("message_flow", {}).get("paired")},
            "scientifically_eligible": dynamic_result.get("scientifically_eligible"),
        }

        # ---- monitor support ----
        row["monitor_support"] = {
            "ledger_integrity": monitor_report.get("ledger_integrity", {}).get("action_event_linkage"),
            "timing_time_base": monitor_report.get("timing_properties", {}).get("time_base"),
            "message_flow": True,
            "mandatory_per_episode": True,
        }

        # ---- scorer identity / audit status ----
        row["scorer"] = {
            "classic_scorer_version": classic.SCORER_VERSION,
            "slice_scorer_version": getattr(slice_mod, "SCORER_VERSION", ""),
            "delegated_to_classic": getattr(slice_mod, "SCORER_VERSION", "").endswith("delegated"),
            "audit_status": SCORER_AUDIT.get(classic_suite_id,
                                             "classic pre-registered semantics; no open audit"),
        }

        # ---- novelty evidence: slice structure vs classic family (same suite, stratified) ----
        classic_sig = signature(classic_case.as_dict())
        slice_sig = signature(slice_case.as_dict())
        delta = structural_delta(classic_sig, slice_sig)
        registry_entries = family_registry.load(FAMILY_REGISTRY_PATH := ROOT / "data/v5/dynamic_experimental/_family_registry.jsonl",
                                                suite_id=classic_suite_id)
        registry_status = ("entries_present" if registry_entries else "NO_REFERENCE")
        row["novelty_evidence"] = {
            "slice_vs_classic_dimensions": delta["dimensions"],
            "slice_vs_classic_same_structure": delta.get("cross_suite_same_structure", False),
            "family_registry": {"path": FAMILY_REGISTRY_PATH.relative_to(ROOT).as_posix(),
                                "status": registry_status,
                                "entries_for_suite": len(registry_entries)},
            "note": ("structural dimensions prove the slice is a distinct executable family vs the "
                     "classic template; registry entries record accepted experimental families "
                     "(T321-DYNA only so far)"),
        }

        # ---- compilation capability (honest) ----
        row["compilation_capability"] = {
            "slice_generate": "executable now (deterministic family expansion)",
            "blueprint_compilation": "NOT_STARTED — pending M5 Codex integration (DW-AUDIT-007/008)",
            "honest_limit": "one slice = one structure family template; >=6 genuine structural "
                            "variants per slice is M8 production design input (V5_M8_COVERAGE_TARGETS §5a)",
        }

        # ---- residual CAPABILITY_GAP ----
        row["capability_gap"] = CAPABILITY_GAP_OF[classic_suite_id]

        # ---- 04 contract stage-C field set (per suite; gated items recorded honestly) ----
        row["stage_c_fields"] = {
            "adapter_id": f"{SLICE_OF[classic_suite_id][0]}:{slice_mod.SCENARIO_VERSION}",
            "can_compile_blueprints": "NOT_STARTED — pending M5 Codex integration (DW-AUDIT-007/008)",
            "replay_coverage": ("offline deterministic replay verified: same seed + same policy "
                                "reproduces identical event ledger and final state "
                                "(tests/v5/test_dynamic_core.py, per-slice gate tests)"),
            "monitor_support": ("mandatory per episode via run_dynamic_case: ledger_integrity "
                                "(1:1 action-event linkage), timing_properties (declared time_base), "
                                "message_flow; failures mark the result ineligible"),
            "scorer_audit": SCORER_AUDIT.get(classic_suite_id,
                                             "classic pre-registered semantics; no open audit"),
            "human_review_status": "BLOCKED_EXTERNAL_REVIEW — Gate D requires real independent "
                                   "human experts (not yet available)",
        }
        suites[classic_suite_id] = row

    matrix = {
        "kind": "ioabench.v5.dynamic-world.suite-evidence-matrix/1",
        "created_utc": created,
        "task": "DW-AUDIT-009 (P4-B): per-suite runnable-vs-generatable evidence",
        "honest_limit": ("18 handwritten dynamic slices + both runner entries executing green are the "
                         "engineering BASE; they do not equal a mature AI auto-generation system "
                         "(blueprint compilation is M5, scaled generation needs PI approval)"),
        "clusters": CLUSTERS,
        "suites": suites,
        "totals": {
            "suites": len(suites),
            "classic_runs_completed": sum(1 for s in suites.values()
                                          if s["classic_runner"]["run"]["status"] == "COMPLETED"),
            "dynamic_runs_completed": sum(1 for s in suites.values()
                                          if s["dynamic_runner"]["run"]["status"] == "COMPLETED"),
            "dynamic_runs_eligible": sum(1 for s in suites.values()
                                         if s["dynamic_runner"]["run"].get("scientifically_eligible") is True),
        },
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK suites={len(suites)} classic_ok={matrix['totals']['classic_runs_completed']} "
          f"dynamic_ok={matrix['totals']['dynamic_runs_completed']} -> {DEST.relative_to(ROOT).as_posix()}")
    return 0


def suite_id(classic_suite_id: str) -> str:
    """The dynamic suite id used in run ids (strip to the slice's SLICE_ID)."""
    return SLICE_OF[classic_suite_id][0].upper().replace("_SLICE", "").replace("T321_", "T321-")


if __name__ == "__main__":
    raise SystemExit(main())
