"""R3 pool revalidation and exact typed-DAG comparison against sealed R1/R2.

Original admissions are read-only; closure eligibility is a separate result.
No hash difference alone establishes novelty, and no reviewer creates facts.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.business_binding import BusinessBinding
from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
from ioabench.v5.ai_generation.bounded_compiler import executable_factors
from ioabench.v5.ai_generation.workflow_novelty import canonical_graph, isomorphism, workflow_graph
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.quality import classify_candidate, dedup_features
from ioabench.v5.evaluation import atomic_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8")


def recorded_runs(directory):
    result = []
    for row in read(directory / "REFERENCE_RESULTS.json"):
        policy = next((name for name in ("witness", "recovery", "naive")
                       if f"-{name}-" in row["run_id"]), None)
        if policy is None:
            raise ValueError("unbound reference policy: " + row["run_id"])
        trace = row["trace"]
        result.append({"arm": row["arm"], "policy": policy,
                       "trace": SimpleNamespace(actions=[SimpleNamespace(**a) for a in trace["actions"]],
                                                events=trace["events"]),
                       "run_id": row["run_id"]})
    return result


def receipt_edges(runs):
    edges = []
    for run in runs:
        produced = {}
        for action in sorted(run["trace"].actions, key=lambda action: action.seq):
            if action.status != "ok":
                continue
            for value in action.arguments.values():
                if isinstance(value, str) and value in produced:
                    edges.append({"run": run["run_id"], "producer_seq": produced[value],
                                  "consumer_seq": action.seq, "receipt_id": value})
            result = action.result or {}
            if result.get("stage_id") and result.get("receipt_id"):
                produced[result["receipt_id"]] = action.seq
    return edges


def historical_graphs():
    frozen = read(RUN / "FROZEN_REFERENCES.json")
    history = []
    for cohort in ("r1_sealed", "r2_sealed"):
        for entry in frozen[cohort]["candidates"]:
            directory = (ROOT if cohort == "r1_sealed" else ROOT / frozen[cohort]["run"]) / entry["evidence_dir"]
            pair = read(directory / "PAIR.json")
            binding_path = directory / "BUSINESS_BINDING.json"
            binding = read(binding_path) if binding_path.exists() else pair[0]["world"].get("business_binding")
            if binding:
                graph, level = workflow_graph(binding), "SEALED_EXECUTABLE_BINDING"
                invariant = None
            else:
                # A missing DAG is UNKNOWN, not an invented empty graph. Actual
                # recorded executions can still give a decisive typed invariant.
                graph, level = None, "HISTORY_GRAPH_UNKNOWN_WITH_OBSERVED_INVARIANT"
                assert all(not case["world"].get("business_binding") for case in pair)
                runs = recorded_runs(directory)
                invariant = {"runtime_stage_receipt_edges": len(receipt_edges(runs)),
                             "reference_runs": len(runs),
                             "execution_sha256": canonical_sha256(read(directory / "REFERENCE_RESULTS.json")),
                             "scope": "SEALED_OBSERVED_REFERENCE_EXECUTIONS_NOT_UNOBSERVED_GRAMMAR"}
            history.append({"candidate": entry["candidate"], "cohort": cohort,
                            "evidence": directory.relative_to(ROOT).as_posix(),
                            "pair_sha256": canonical_sha256(pair), "graph": graph,
                            "compatibility": level, "observed_invariant": invariant,
                            "family_id": canonical_graph(graph)["family_id"] if graph is not None else None})
    return history


def main():
    history, rows, seen, unique, prior_instances = historical_graphs(), [], [], set(), []
    admissions = sorted(RUN.glob("**/reviews/*/ADMISSION.json"), key=lambda path:
        read(path.parents[2] / "candidates" / path.parent.name / "RESULT.json").get("finished_utc", ""))
    for path in admissions:
        record = read(path)
        if record.get("status") != "DEV_ACCEPTED":
            continue
        directory = path.parents[2] / "candidates" / path.parent.name
        result, pair = read(directory / "RESULT.json"), read(directory / "PAIR.json")
        candidate = path.parent.name
        if candidate in unique:
            continue
        unique.add(candidate)
        binding = BusinessBinding.from_dict(read(directory / "BUSINESS_BINDING.json"))
        graph = workflow_graph(binding)
        canonical = canonical_graph(graph)
        runs = recorded_runs(directory)
        claims = business_witnesses(binding, runs)
        errors = []
        if not claims or any(claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL" for claim in claims):
            errors.append("CURRENT_STRICT_BUSINESS_WITNESS_FAILED")
        doc_path = directory / "WORKFLOW_PLAN_MODEL_DOC.json"
        if doc_path.exists():
            plan = read(doc_path)["plan"]
            by_id = {step["stage_id"]: step for step in binding.plan}
            for edge in plan["edges"]:
                if edge["from"] not in by_id[edge["to"]]["requires"]:
                    errors.append("DECLARED_EDGE_NOT_CONSUMED:" + edge["from"] + "->" + edge["to"])
        scenario = suite_spec(result["task"]["suite"], typed=True).scenario_factory()
        prior = [item for item in prior_instances if item["suite"] == result["task"]["suite"]]
        instance_checks = [classify_candidate(case, [item["features"] for item in prior], scenario=scenario)
                           for case in pair]
        for check in instance_checks:
            overlaps = []
            for neighbor in check["nearest_neighbors"]:
                if neighbor["exact_duplicate"] or (not neighbor["dimensions"] and neighbor["text_similarity"] >= 0.9):
                    other = prior[neighbor["reference_index"]]
                    mapping = isomorphism(graph, other["graph"])
                    overlaps.append({"candidate": other["candidate"], "case_id": other["case_id"],
                                     "exact_duplicate": neighbor["exact_duplicate"],
                                     "text_similarity": neighbor["text_similarity"], "typed_graph_mapping": mapping})
                    # The legacy feature projection omits stage dependencies.
                    # Exact duplicates and text-near cases in the SAME graph still fail.
                    if neighbor["exact_duplicate"] or mapping is not None:
                        errors.append("PRIOR_R3_INSTANCE_DUPLICATE")
            check["text_neighbor_graph_comparisons"] = overlaps
        assert classify_candidate(pair[0], [dedup_features(pair[0], scenario=scenario)], scenario=scenario)["status"] == "EXACT_DUPLICATE"
        matches, comparisons = [], []
        observed_edges = receipt_edges(runs)
        for other in history + seen:
            if other["graph"] is None:
                invariant = other["observed_invariant"]
                certified = bool(observed_edges) and invariant["runtime_stage_receipt_edges"] == 0 and invariant["reference_runs"] >= 6
                comparisons.append({"candidate": other["candidate"], "cohort": other["cohort"],
                                    "isomorphic": False if certified else None,
                                    "proof": "NONISOMORPHIC_OBSERVED_RECEIPT_EDGE_INVARIANT" if certified else "HISTORY_GRAPH_UNKNOWN",
                                    "candidate_runtime_receipt_edges": len(observed_edges),
                                    "historical_invariant": invariant})
                continue
            mapping = isomorphism(graph, other["graph"])
            comparison = {"candidate": other["candidate"], "cohort": other["cohort"],
                          "isomorphic": mapping is not None, "node_mapping": mapping,
                          "family_id": other["family_id"]}
            comparisons.append(comparison)
            if mapping is not None:
                matches.append(comparison)
        historical_matches = [item for item in matches if item["cohort"] != "R3"]
        unknown = [item for item in comparisons if item.get("isomorphic") is None]
        if unknown:
            errors.append("HISTORY_GRAPH_UNKNOWN")
        business_tools = {tool["tool"] for tool in binding.tools}
        mechanism_projection = {
            "compiler_factors": executable_factors(result["task"]["suite"], pair[0]["world"]),
            "observed_policy_actions": [{"arm": run["arm"], "policy": run["policy"],
                "tools": [(action.tool, action.status) for action in run["trace"].actions
                          if action.tool not in business_tools]} for run in runs]}
        row = {"candidate": candidate, "suite": result["task"]["suite"],
               "route": result["route"], "admission": record["status"],
               "closure_eligible": not errors, "closure_errors": errors,
               "workflow_family_id": canonical["family_id"],
               "family_status": "HISTORICAL_FAMILY" if historical_matches else
                                "NEW_INSTANCE_WITHIN_R3_FAMILY" if matches else "NEW_VS_R1_R2_AND_PRIOR_R3",
               "isomorphic_to": matches, "historical_scope": "17_SEALED_R1_R2_PAIRS_DECLARED_BUSINESS_DAGS",
               "new_vs_frozen_history": not historical_matches and not unknown,
               "executed_receipt_edges": observed_edges,
               "instance_hashes": [canonical_sha256(case) for case in pair],
               "instance_history": read(directory / "HISTORY_DEDUP.json"),
               "prior_r3_instance_history": {"prior_cases": [{k: item[k] for k in ("candidate", "case_id")}
                                                            for item in prior], "checks": instance_checks},
               "mechanism_signature": canonical_sha256(mechanism_projection),
               "mechanism_projection": mechanism_projection,
               "legacy_combined_signature": result.get("structural_signature_sha256"),
               "execution_trace_refs": [{"file": (directory / "REFERENCE_RESULTS.json").relative_to(ROOT).as_posix(),
                                         "run_id": run["run_id"], "arm": run["arm"], "policy": run["policy"]}
                                        for run in runs],
               "comparisons": comparisons, "graph": graph,
               "business_workflow_hash": binding.canonical_workflow_hash,
               "evidence": directory.relative_to(ROOT).as_posix(),
               "business_witnesses": claims, "formal_accepted": False,
               "same_model_audit_independent_science": False,
               "simulation_only": result["task"]["suite"] in {"T361", "T362", "T363"},
               "evidence_limitations": ["Global undeclared historical workflows are not inferred; scope is sealed R1/R2 declared DAGs.",
                                        "Mechanism diversity is separate from business workflow graph identity."]}
        rows.append(row)
        seen.append({"candidate": candidate, "cohort": "R3", "graph": graph,
                     "family_id": canonical["family_id"]})
        prior_instances.extend({"candidate": candidate, "suite": result["task"]["suite"],
                                "case_id": case["case_id"], "features": dedup_features(case, scenario=scenario),
                                "graph": graph}
                               for case in pair)
    per_suite = {}
    for suite in ("T321", "T331", "T362"):
        group = [row for row in rows if row["suite"] == suite and row["route"] == "compositional_r3"]
        eligible = [row for row in group if row["closure_eligible"]]
        families = {row["workflow_family_id"] for row in eligible if row["new_vs_frozen_history"]}
        per_suite[suite] = {"accepted_pairs": len(group), "closure_eligible_pairs": len(eligible),
                            "new_family_ids": sorted(families),
                            "meets_goal": len(eligible) >= 2 and len(families) >= 2}
    atomic_json(RUN / "WORKFLOW_NOVELTY_AUDIT.json", {
        "version": "ioabench.v5.r3.workflow-novelty-audit/2.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "historical_compatibility": history, "rows": rows, "per_suite": per_suite})
    jsonl(RUN / "R3_DEV_POOL_INDEX.jsonl", [{k: v for k, v in row.items()
           if k not in {"graph", "business_witnesses", "instance_history", "comparisons"}} for row in rows])
    jsonl(RUN / "STRUCTURE_FAMILY_INDEX.jsonl", history + seen)
    print(json.dumps({"unique_admitted_pairs": len(rows), "per_suite": per_suite}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
