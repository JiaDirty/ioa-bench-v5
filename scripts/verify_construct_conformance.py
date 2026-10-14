"""Machine-readable Construct Contract Conformance for all 18 suites.

Executes every suite through its canonical causal runtime on a generated case
and validates the suite contract field by field.  Emits per-suite, per-
dimension evidence to artifacts/gates/CONSTRUCT_CONFORMANCE_V2.json.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.models import ModelProfile  # noqa: E402

PROFILE = ModelProfile("mock", "construct-conformance", {"tools": True}, {})
FORBIDDEN_MARKERS = ("oracle_payload", "ground_truth", "scoring_rules", "hidden_truth", "attack_label")

# Per-suite runtime business tools beyond the contract verbs (environment and
# business-layer actions the runtimes legitimately expose).
EXTRA_TOOLS: dict[str, set[str]] = {
    "T311": {"dispatch_task", "revoke_delegation", "select_alternative", "query_capability_evidence", "query_issuer", "inspect_agent_card", "discover_agents", "delegate", "select_agent", "execute_business_action"},
    "T312": {"discover_candidates", "inspect_record"},
    "T313": {"inspect_chain", "attenuate", "delegate", "trace_parent", "request_reconstruction", "verify_grant", "pause", "execute", "dispatch"},
    "T321": {"offer", "check_capabilities", "accept", "reject", "fallback", "create", "query_status", "cancel", "retry", "compensate", "execute"},
    "T322": {"offer", "check_capabilities", "accept", "reject", "fallback", "create", "query_status", "cancel", "retry", "compensate", "execute"},
    "T323": {"inspect_chain", "attenuate", "delegate", "trace_parent", "request_reconstruction", "verify_grant", "pause", "execute", "dispatch"},
    "T331": {"apply_update", "block", "inspect_message", "inspect_claim", "quote", "endorse", "flag", "request_source", "retract", "verify_source", "correct", "forward", "verify", "verify"},
    "T332": {"inspect_scope", "inspect_metadata", "disclose_nodes", "send_contact", "retract", "submit_inference", "qualify_confidence", "share", "withhold", "accept"},
    "T333": {"inspect_scope", "inspect_metadata", "disclose_nodes", "send_contact", "retract", "submit_inference", "qualify_confidence", "share", "withhold", "accept"},
    "T341": {"share_evidence", "preserve_minority", "state_position", "decide", "revise", "observe_norm", "challenge_norm", "adopt", "correct_norm", "challenge", "quote_evidence", "vote"},
    "T342": {"inspect_message", "verify_source", "forward", "quote", "endorse", "flag", "correct", "retract", "inspect_claim", "block", "request_source", "verify"},
    "T343": {"share_evidence", "preserve_minority", "state_position", "decide", "revise", "observe_norm", "challenge_norm", "adopt", "correct_norm", "observe", "consult_policy", "challenge", "correct"},
    "T351": {"inspect_offer", "verify_cost", "accept_offer", "decline_offer", "approve_offer", "execute", "report"},
    "T352": {"observe_registry", "verify_quality", "select_agent", "confirm_selection", "switch", "record_feedback", "execute"},
    "T353": {"discover_candidates", "inspect_record", "compare_candidates", "select_candidate", "execute_task"},
    "T361": {"recommend", "express_uncertainty", "invite_check", "revise", "request_persona_check", "challenge"},
    "T362": {"post", "reply", "quote", "endorse", "rank", "challenge"},
    "T363": {"assist", "explain", "request_persona_check", "withdraw", "challenge"},
}

# Evidence markers proving each scripted (environment) actor exists in the world.
SCRIPTED_ROLE_EVIDENCE: dict[str, dict[str, list[str]]] = {
    "T311": {"scripted_registry_peer": ["registry", "peer", "directory"]},
    "T312": {"scripted_registry": ["registry", "directory", "entries"]},
    "T313": {"scripted_grant_source": ["grant", "chain", "issuer"]},
    "T321": {"scripted_offer_source": ["offer", "capability"]},
    "T322": {"scripted_gateway": ["gateway", "mapping", "receipt"]},
    "T323": {"scripted_grant_source": ["grant", "chain", "issuer"], "scripted_tool": ["tool", "resource", "business"]},
    "T331": {"scripted_seed": ["initial_message", "seed", "message"]},
    "T332": {"scripted_metadata_source": ["directory", "metadata", "nodes"], "scripted_querier": ["recipient", "querier", "contact"]},
    "T333": {"scripted_metadata_source": ["traces", "metadata", "tenant"]},
    "T341": {"scripted_source": ["receipts", "ledger", "source"]},
    "T342": {"scripted_source": ["initial_message", "claim", "source"]},
    "T343": {"scripted_policy_source": ["policy", "approval", "receipt"]},
    "T351": {"scripted_reward_source": ["offer", "reward", "validation"]},
    "T352": {"scripted_feedback_source": ["feedback", "quality", "reputation"]},
    "T353": {"scripted_router": ["router", "ranking", "candidate"]},
}

# contract verb -> runtime tool name (identity when omitted)
ACTION_MAPS: dict[str, dict[str, str]] = {
    "T312": {"discover": "discover_candidates", "crosscheck": "compare_candidates", "trial": "inspect_record",
             "select": "select_candidate", "execute": "execute_task", "inspect": "inspect_record"},
    "T313": {"reject": "pause", "revoke": "pause"},
    "T321": {},
    "T322": {},
    "T323": {"reject": "pause", "revoke": "pause"},
    "T331": {"verify": "verify_source", "isolate": "block", "rollback": "retract"},
    "T332": {},
    "T333": {},
    "T341": {"vote": "decide", "quote": "share_evidence", "verify": "challenge"},
    "T342": {},
    "T343": {"observe": "observe_norm", "consult_policy": "challenge_norm", "correct": "correct_norm"},
    "T351": {"verify": "verify_cost", "take_shortcut": "accept_offer", "report": "report"},
    "T352": {"discover": "observe_registry", "compare": "verify_quality", "select": "select_agent", "execute": "execute"},
    "T353": {"inspect_candidates": "inspect_record", "compare": "compare_candidates", "select": "select_candidate",
             "execute": "execute_task"},
    "T361": {},
    "T362": {},
    "T363": {},
}

SUITES: dict[str, dict[str, Any]] = {
    "T311": {"generator": ("ioabench.suites.t311.generation", "T311Generator"),
             "adapter": ("ioabench.runtime.t311_fixture", "build_t311_case_from_skeleton"),
             "executor": ("ioabench.runtime.t311_construct", "execute_t311"),
             "baseline": ("ioabench.runtime.t311_baselines", "T311Baseline"),
             "baseline_policies": {"safe": "safe", "naive": "naive", "recovery": "recovery"}},
    "T312": {"generator": ("ioabench.suites.t312.generation", "T312Generator"),
             "adapter": ("ioabench.runtime.discovery_selection", "build_discovery_case_from_skeleton"),
             "executor": ("ioabench.runtime.discovery_selection", "execute_discovery_selection"),
             "baseline": ("ioabench.runtime.discovery_selection", "DiscoverySelectionBaseline")},
    "T313": {"generator": ("ioabench.suites.t313.generation", "T313Generator"),
             "adapter": ("ioabench.runtime.delegation_provenance", "build_delegation_case_from_skeleton"),
             "executor": ("ioabench.runtime.delegation_provenance", "execute_delegation"),
             "baseline": ("ioabench.runtime.delegation_provenance", "DelegationBaseline")},
    "T321": {"generator": ("ioabench.suites.t321.generation", "T321Generator"),
             "adapter": ("ioabench.runtime.protocol_state_machine", "build_protocol_case_from_skeleton"),
             "executor": ("ioabench.runtime.protocol_state_machine", "execute_protocol"),
             "baseline": ("ioabench.runtime.protocol_state_machine", "ProtocolBaseline")},
    "T322": {"generator": ("ioabench.suites.t322.generation", "T322Generator"),
             "adapter": ("ioabench.runtime.protocol_state_machine", "build_protocol_case_from_skeleton"),
             "executor": ("ioabench.runtime.protocol_state_machine", "execute_protocol"),
             "baseline": ("ioabench.runtime.protocol_state_machine", "ProtocolBaseline")},
    "T323": {"generator": ("ioabench.suites.t323.generation", "T323Generator"),
             "adapter": ("ioabench.runtime.delegation_provenance", "build_delegation_case_from_skeleton"),
             "executor": ("ioabench.runtime.delegation_provenance", "execute_delegation"),
             "baseline": ("ioabench.runtime.delegation_provenance", "DelegationBaseline")},
    "T331": {"generator": ("ioabench.suites.t331.generation", "T331Generator"),
             "adapter": ("ioabench.runtime.network_propagation", "build_propagation_case_from_skeleton"),
             "executor": ("ioabench.runtime.network_propagation", "execute_propagation"),
             "baseline": ("ioabench.runtime.network_propagation", "PropagationBaseline")},
    "T332": {"generator": ("ioabench.suites.t332.generation", "T332Generator"),
             "adapter": ("ioabench.runtime.disclosure_inference", "build_disclosure_case_from_skeleton"),
             "executor": ("ioabench.runtime.disclosure_inference", "execute_disclosure"),
             "baseline": ("ioabench.runtime.disclosure_inference", "DisclosureBaseline")},
    "T333": {"generator": ("ioabench.suites.t333.generation", "T333Generator"),
             "adapter": ("ioabench.runtime.disclosure_inference", "build_disclosure_case_from_skeleton"),
             "executor": ("ioabench.runtime.disclosure_inference", "execute_disclosure"),
             "baseline": ("ioabench.runtime.disclosure_inference", "DisclosureBaseline")},
    "T341": {"generator": ("ioabench.suites.t341.generation", "T341Generator"),
             "adapter": ("ioabench.runtime.deliberation_norm", "build_deliberation_case_from_skeleton"),
             "executor": ("ioabench.runtime.deliberation_norm", "execute_deliberation"),
             "baseline": ("ioabench.runtime.deliberation_norm", "DeliberationBaseline")},
    "T342": {"generator": ("ioabench.suites.t342.generation", "T342Generator"),
             "adapter": ("ioabench.runtime.network_propagation", "build_propagation_case_from_skeleton"),
             "executor": ("ioabench.runtime.network_propagation", "execute_propagation"),
             "baseline": ("ioabench.runtime.network_propagation", "PropagationBaseline")},
    "T343": {"generator": ("ioabench.suites.t343.generation", "T343Generator"),
             "adapter": ("ioabench.runtime.deliberation_norm", "build_deliberation_case_from_skeleton"),
             "executor": ("ioabench.runtime.deliberation_norm", "execute_deliberation"),
             "baseline": ("ioabench.runtime.deliberation_norm", "DeliberationBaseline")},
    "T351": {"generator": ("ioabench.suites.t351.generation", "T351Generator"),
             "adapter": ("ioabench.runtime.incentive_reputation", "build_incentive_case_from_skeleton"),
             "executor": ("ioabench.runtime.incentive_reputation", "execute_incentive_reputation"),
             "baseline": ("ioabench.runtime.incentive_reputation", "IncentiveReputationBaseline")},
    "T352": {"generator": ("ioabench.suites.t352.generation", "T352Generator"),
             "adapter": ("ioabench.runtime.incentive_reputation", "build_incentive_case_from_skeleton"),
             "executor": ("ioabench.runtime.incentive_reputation", "execute_incentive_reputation"),
             "baseline": ("ioabench.runtime.incentive_reputation", "IncentiveReputationBaseline")},
    "T353": {"generator": ("ioabench.suites.t353.generation", "T353Generator"),
             "adapter": ("ioabench.runtime.discovery_selection", "build_discovery_case_from_skeleton"),
             "executor": ("ioabench.runtime.discovery_selection", "execute_discovery_selection"),
             "baseline": ("ioabench.runtime.discovery_selection", "DiscoverySelectionBaseline")},
    "T361": {"generator": ("ioabench.suites.t361.generation", "T361Generator"),
             "adapter": ("ioabench.runtime.human_agency_simulation", "build_agency_case_from_skeleton"),
             "executor": ("ioabench.runtime.human_agency_simulation", "execute_agency"),
             "baseline": ("ioabench.runtime.human_agency_simulation", "AgencyBaseline")},
    "T362": {"generator": ("ioabench.suites.t362.generation", "T362Generator"),
             "adapter": ("ioabench.runtime.human_agency_simulation", "build_agency_case_from_skeleton"),
             "executor": ("ioabench.runtime.human_agency_simulation", "execute_agency"),
             "baseline": ("ioabench.runtime.human_agency_simulation", "AgencyBaseline")},
    "T363": {"generator": ("ioabench.suites.t363.generation", "T363Generator"),
             "adapter": ("ioabench.runtime.human_agency_simulation", "build_agency_case_from_skeleton"),
             "executor": ("ioabench.runtime.human_agency_simulation", "execute_agency"),
             "baseline": ("ioabench.runtime.human_agency_simulation", "AgencyBaseline")},
}
SIMULATION_SUITES = {"T361", "T362", "T363"}


def load(module_name: str, attribute: str) -> Any:
    return getattr(importlib.import_module(module_name), attribute)


def build_case(suite: str) -> dict[str, Any]:
    config = SUITES[suite]
    generator = load(*config["generator"])()
    skeleton = asdict(generator.generate(seed=29, mechanism_index=0, difficulty="medium", condition="RISK"))
    return load(*config["adapter"])(skeleton)


async def run_policy(suite: str, case: dict[str, Any], policy: str) -> dict[str, Any]:
    config = SUITES[suite]
    baseline_type = load(*config["baseline"])
    if suite == "T311":
        model = baseline_type({"unsafe": "naive"}.get(policy, policy))
    else:
        model = baseline_type(policy)
    executor = load(*config["executor"])
    return await executor(ROOT, case, model, PROFILE, run_id=f"{suite}-conformance-{policy}")


def dimension(passed: bool, evidence: Any) -> dict[str, Any]:
    return {"pass": bool(passed), "evidence": evidence}


def check_suite(suite: str, contract: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        case = build_case(suite)
        results = {policy: asyncio.run(run_policy(suite, deepcopy(case), policy))
                   for policy in ("safe", "naive", "recovery")}
    except Exception as exc:  # noqa: BLE001 - conformance evidence must capture the failure
        return {"pass": False, "error": f"{type(exc).__name__}: {exc}"}

    safe, naive, recovery = results["safe"], results["naive"], results["recovery"]
    replay = safe["replay"]
    world = replay["world_snapshot"]
    initial = replay["scenario"].get("initial_world", {})
    actions = replay["scorer_inputs"]["actions"]
    records = replay["model_records"]
    score = safe["score"]

    tested_agents = [agent for agent in replay["agents"] if agent.get("model_role") == "TESTED"]
    checks["minimum_tested_agents"] = dimension(
        len(tested_agents) >= contract["minimum_tested_agent_count"],
        {"tested": sorted(agent["agent_id"] for agent in tested_agents),
         "required": contract["minimum_tested_agent_count"]})

    roles = contract["required_actor_roles"]
    tested_roles = [role for role in roles if role.startswith("tested_")]
    scripted_roles = [role for role in roles if role.startswith("scripted_")]
    model_agent_ids = {record["agent_id"] for record in records}
    timeline_actors = {event.get("actor_agent_id") for event in replay["timeline"]}
    search_space = " | ".join(sorted(timeline_actors | set(world.keys()))).lower()
    case_space = json.dumps(case, default=str).lower()
    scripted_ok = True
    missing_scripted = []
    for role in scripted_roles:
        tokens = SCRIPTED_ROLE_EVIDENCE.get(suite, {}).get(role) or [token for token in role.replace("scripted_", "").split("_")]
        if not any(token.lower() in search_space or token.lower() in case_space for token in tokens):
            scripted_ok = False
            missing_scripted.append(role)
    tested_ok = len(tested_agents) >= max(len(tested_roles), contract["minimum_tested_agent_count"])
    no_extra_models = model_agent_ids <= {agent["agent_id"] for agent in tested_agents}
    checks["required_actor_roles"] = dimension(
        tested_ok and scripted_ok and no_extra_models,
        {"roles": roles, "tested_agents": sorted(agent["agent_id"] for agent in tested_agents),
         "model_record_agents": sorted(model_agent_ids), "missing_scripted_evidence": missing_scripted})

    checks["environment_state"] = dimension(
        bool(initial) and bool(world),
        {"initial_keys": sorted(initial.keys())[:10], "world_keys": sorted(world.keys())[:12]})

    request_blobs = [json.dumps(record["request"], sort_keys=True) for record in records]
    checks["model_visible_evidence"] = dimension(
        bool(records) and any(len(blob) > 100 for blob in request_blobs),
        {"model_records": len(records), "request_bytes": [len(blob) for blob in request_blobs[:4]]})

    mapped_verbs = {ACTION_MAPS.get(suite, {}).get(verb, verb) for verb in contract["allowed_model_actions"]}
    executed = {action["type"] for action in actions if action.get("status") == "OK"}
    permitted_universe = mapped_verbs | EXTRA_TOOLS.get(suite, set())
    outside = sorted(executed - permitted_universe)
    checks["allowed_actions_respected"] = dimension(
        bool(executed) and not outside,
        {"executed": sorted(executed), "contract_verbs_supported": sorted(mapped_verbs & (executed | permitted_universe)),
         "outside_actions": outside})

    transitions_observed = world != initial
    transition_keys = [key for key in world if any(token in key for token in ("log", "history", "state", "persona", "visibility", "curve", "episodes", "votes", "norm"))]
    checks["state_transitions"] = dimension(
        transitions_observed,
        {"world_differs_from_initial": transitions_observed, "stateful_keys": sorted(transition_keys)[:10]})

    checks["safe_condition"] = dimension(
        safe["score"]["outcome_class"] in {"EARLY_SAFE", "LATE_RECOVERY"} and safe["score"]["task_utility"] is True,
        {"outcome": safe["score"]["outcome_class"], "task_utility": safe["score"]["task_utility"]})
    checks["unsafe_condition"] = dimension(
        naive["score"]["outcome_class"] in {"UNSAFE_ACTION", "FULL_FAILURE"},
        {"outcome": naive["score"]["outcome_class"], "task_utility": naive["score"]["task_utility"],
         "note": "utility may legitimately coexist with unsafe behavior; separation is checked separately"})
    checks["recovery_condition"] = dimension(
        recovery["score"]["outcome_class"] == "LATE_RECOVERY",
        {"outcome": recovery["score"]["outcome_class"]})

    checks["task_utility_separate"] = dimension(
        isinstance(score.get("task_utility"), bool) and "task_utility" in naive["score"],
        {"safe_utility": score.get("task_utility"), "naive_utility": naive["score"].get("task_utility")})

    missing_metrics = [metric for metric in contract["required_raw_metrics"]
                       if metric != "SIMULATION_ONLY" and metric not in score]
    checks["required_raw_metrics"] = dimension(
        not missing_metrics, {"missing": missing_metrics, "present": sorted(score.keys())[:16]})

    checks["scorer_inputs"] = dimension(
        isinstance(replay["scorer_inputs"].get("actions"), list) and isinstance(replay["scorer_inputs"].get("score"), dict),
        {"action_count": len(replay["scorer_inputs"]["actions"])})

    checks["minimum_interaction_depth"] = dimension(
        len(records) >= contract["minimum_interaction_depth"],
        {"model_calls": len(records), "required": contract["minimum_interaction_depth"]})

    hashes_ok = all(canonical_sha256(record["request"]) == record["request_sha256"] for record in records)
    bundle_complete = all(key in replay for key in ("timeline", "model_records", "scenario", "world_snapshot"))
    checks["replay_requirements"] = dimension(
        hashes_ok and bundle_complete and bool(replay["scenario"].get("manifest")),
        {"immutable_request_hashes": hashes_ok, "bundle_sections": sorted(replay.keys())})

    leaks = [marker for marker in FORBIDDEN_MARKERS if any(marker in blob for blob in request_blobs)]
    checks["forbidden_shortcuts"] = dimension(not leaks, {"leaked_markers": leaks})

    if suite in SIMULATION_SUITES:
        simulation_labeled = (replay["scenario"].get("simulation_only") is True
                              and score.get("simulation_only") is True
                              and safe.get("eligibility") == "SIMULATION_ONLY")
        checks["simulation_only_label"] = dimension(simulation_labeled,
                                                    {"scenario": replay["scenario"].get("simulation_only"),
                                                     "score": score.get("simulation_only"),
                                                     "eligibility": safe.get("eligibility")})
        persona_in_records = [record["agent_id"] for record in records
                              if "persona" in str(record["agent_id"])]
        checks["persona_not_model"] = dimension(not persona_in_records, {"persona_model_records": persona_in_records})
    else:
        checks["no_simulation_claim"] = dimension(score.get("simulation_only") is not True,
                                                  {"score_label": score.get("simulation_only")})

    return {"pass": all(item["pass"] for item in checks.values()), "dimensions": checks}


def main() -> int:
    results: dict[str, Any] = {"generated_by": "scripts/verify_construct_conformance.py",
                               "contract_schema": "contracts/schema/construct.schema.json",
                               "suites": {}}
    for suite in sorted(SUITES):
        contract = json.loads((ROOT / "contracts" / "constructs" / f"{suite}.json").read_text(encoding="utf-8"))
        print(f"[conformance] {suite} ...", flush=True)
        results["suites"][suite] = check_suite(suite, contract)
    results["overall_pass"] = all(item["pass"] for item in results["suites"].values())
    results["passed_suites"] = sorted(s for s, item in results["suites"].items() if item["pass"])
    results["failed_suites"] = sorted(s for s, item in results["suites"].items() if not item["pass"])
    output = ROOT / "artifacts" / "gates" / "CONSTRUCT_CONFORMANCE_V2.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"overall_pass={results['overall_pass']} failed={results['failed_suites']}")
    return 0 if results["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
