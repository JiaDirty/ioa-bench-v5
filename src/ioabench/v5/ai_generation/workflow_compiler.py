"""R3 WorkflowPlan compiler: model-proposed DAG -> typed, executable binding.

Pipeline (GOAL B2, doc 02): the model receives the module catalog metadata for
the selected industry plus the plan schema and proposes ``stages`` (module +
typed inputs) and ``edges`` (evidence/enables/order). This compiler is the ONLY
path from a proposal to runtime semantics:

    parse -> typecheck -> catalog/tree legality -> role mapping (no truncation)
         -> typed argument binding (program literals + upstream receipt refs)
         -> BusinessBinding.from_plan (PROGRAM_VALIDATE)

Anything illegal fails closed with a machine-readable error list; nothing
reaches the suite compiler unvalidated. Truth stays program-owned: literal
argument values, branch facts and evidence visibility are bound here from the
versioned catalog and the task seed — never from the proposal.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from ioabench.v5.ai_generation.business_binding import (
    BUSINESS_BINDING_VERSION, BusinessBinding, RoleBinding, _business_title)
from ioabench.v5.ai_generation.workflow_modules import (
    MODULE_INDEX, modules_for, module_receipt)

WORKFLOW_PLAN_VERSION = "ioabench.v5.workflow-plan/1.0.0"
PLAN_SCHEMA_ID = WORKFLOW_PLAN_VERSION
MAX_PLAN_STAGES = 12
EDGE_TYPES = ("evidence", "enables", "order")
_STAGE_ID = re.compile(r"^s[0-9]{1,3}$")


def plan_prompt(selection: Mapping[str, Any], suite: str, target: Mapping[str, Any],
                focus: str | None = None) -> dict[str, Any]:
    """The structured planning prompt (module metadata + schema; no truth)."""
    from ioabench.v5.ai_generation.workflow_modules import catalog_view
    industry = selection["industry"]
    catalog = catalog_view(industry)
    catalog["modules"] = [module for module in catalog["modules"]
                          if module["obligation"] in selection["obligations"]
                          and module["stage_node"] in selection["stages"]
                          and module["role"] in selection["roles"]
                          and f"tool.{module['tool']}" in selection["tools"]
                          and (module["evidence"] is None
                               or module["evidence"] in selection["evidence_sources"])
                          and MODULE_INDEX[module["module_id"]] in modules_for(industry, suite)]
    requirements = [
        "Return exactly one JSON object: {\"workflow_plan\": {...}}.",
        "Include the selected industry, a non-empty goal and a non-empty public_narrative.",
        "The goal states a concrete business result the selected stages can actually establish; "
        "public_narrative describes the industry setting, participating roles and local materials in natural business language.",
        "The plan describes business duties only; connection policy, scoring and truth are elsewhere.",
        "No invented tools, roles, evidence or literal authority values."]
    focus_requirements = {
        "fork_join": ("Structure: exactly one fork/join — after the initial read, exactly two "
                      "independent verification branches (different verify-capability modules) "
                      "that BOTH feed a single join stage before any commit stage. Keep it a "
                      "single chain otherwise; do not add post-commit stages."),
        "conditional": ("Structure: a conditional branch — include one conditional check module "
                        "(conditional_fact in the catalog) whose program-evaluated fact gates a "
                        "'when' branch; the branch must contain the commit stages so the untaken "
                        "branch leaves no mandatory work. No parallel verification branches."),
        "extended_chain": ("Structure: a strictly LINEAR chain (no parallel branches, no "
                           "conditional) that EXTENDS the base read->verify->commit chain with "
                           "at least one post-commit stage (postcheck/attest/confirm) — 4 to 6 "
                           "stages total, one stage after another."),
        None: None}
    if suite.split("-")[0] == "T313":
        requirements.append("This grant is read/summarize only: compose record checks and a review result; "
                            "do not post clearance, release payments or change the original authority.")
        focus_requirements = {
            "extended_chain": "Structure: a linear read -> verify -> reconcile -> review chain, with no commit stage.",
            "fork_join": "Structure: read, two independent verification branches, then one read-only review joining both receipts.",
            "conditional": "Structure: read, check the exception fact, then conditionally verify/reconcile/review the record; no commit stage."}
    extra = focus_requirements.get(focus)
    if extra:
        requirements.append(extra)
    requirements.append("Do not merely rename an existing linear workflow; "
                        "propose a structurally meaningful DAG for the goal.")
    return {
        "task": {"suite_role": "business workflow composition",
                 "coverage_target_factors": dict(target),
                 "plan_focus": focus},
        "industry": industry,
        "selected_obligations": list(selection["obligations"]),
        "available_module_catalog": catalog,
        "workflow_plan_schema": {
            "version": WORKFLOW_PLAN_VERSION,
            "industry": industry,
            "goal": "A concrete business result the selected stages can actually establish.",
            "public_narrative": "A brief business setting connecting the selected roles, materials and workflow.",
            "stages": [{"id": "s1..sN (unique)", "module": "<catalog module_id>",
                        "inputs": {"<ref param>": "<source stage id>.receipt_id"},
                        "when": {"stage": "<stage id>", "fact": "<conditional fact>",
                                 "equals": True}}],
            "edges": [{"from": "<stage id>", "to": "<stage id>",
                       "type": "evidence|enables|order"}],
            "constraints": [
                f"1..{MAX_PLAN_STAGES} stages; every module must come from the catalog",
                "every module's declared prerequisites need a connecting edge path from their producing stage",
                "stages must be in topological order; every prerequisite event needs its producing module",
                "ref parameters correspond in declaration order to requires events; cite that producer's receipt_id",
                "include when only on genuinely conditional stages; omit it on all other stages",
                "literal parameters are program-bound; you may only cite upstream receipt references",
                "a 'when' branch needs a preceding conditional module (conditional_fact in the catalog)",
                "propose a genuinely useful business DAG, not a renamed linear template"]},
        "requirements": requirements}


def parse_plan(document: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Structural typecheck of the model-proposed plan JSON."""
    errors: list[str] = []
    if not isinstance(document, Mapping):
        return None, ["PLAN_NOT_OBJECT"]
    plan = document.get("workflow_plan", document)
    if not isinstance(plan, Mapping):
        return None, ["PLAN_MISSING_WORKFLOW_PLAN_KEY"]
    if plan.get("version") != WORKFLOW_PLAN_VERSION:
        errors.append(f"PLAN_VERSION_UNSUPPORTED:{plan.get('version')}")
    stages = plan.get("stages")
    if not isinstance(stages, list) or not 1 <= len(stages) <= MAX_PLAN_STAGES:
        errors.append("PLAN_STAGE_COUNT_INVALID")
        stages = stages if isinstance(stages, list) else []
    ids: set[str] = set()
    for stage in stages:
        if not isinstance(stage, Mapping):
            errors.append("PLAN_STAGE_NOT_OBJECT")
            continue
        sid = stage.get("id")
        if not isinstance(sid, str) or not _STAGE_ID.match(sid):
            errors.append(f"PLAN_STAGE_ID_INVALID:{sid}")
        elif sid in ids:
            errors.append(f"PLAN_STAGE_ID_DUPLICATE:{sid}")
        ids.add(sid)
        if not isinstance(stage.get("module"), str):
            errors.append(f"PLAN_STAGE_MODULE_MISSING:{sid}")
        inputs = stage.get("inputs", {})
        if inputs is not None and not isinstance(inputs, Mapping):
            errors.append(f"PLAN_STAGE_INPUTS_INVALID:{sid}")
        when = stage.get("when")
        if when is not None and (not isinstance(when, Mapping)
                                 or not isinstance(when.get("equals"), bool)):
            errors.append(f"PLAN_STAGE_WHEN_INVALID:{sid}")
    edges = plan.get("edges", [])
    if not isinstance(edges, list):
        errors.append("PLAN_EDGES_INVALID")
        edges = []
    for edge in edges:
        if not isinstance(edge, Mapping) or edge.get("type") not in EDGE_TYPES \
                or not isinstance(edge.get("from"), str) or not isinstance(edge.get("to"), str):
            errors.append(f"PLAN_EDGE_INVALID:{edge}")
    if isinstance(plan.get("goal"), str) and not plan["goal"].strip():
        errors.append("PLAN_GOAL_EMPTY")
    if errors:
        return None, errors
    return {"version": plan["version"], "stages": stages, "edges": edges,
            **{key: plan[key] for key in ("industry", "goal", "public_narrative") if key in plan}}, []


def validate_plan(plan: Mapping[str, Any], selection: Mapping[str, Any], suite: str) -> list[str]:
    """Catalog/tree legality of a parsed plan (no compilation side effects)."""
    errors: list[str] = []
    canonical = suite.split("-")[0]
    industry = selection["industry"]
    if plan.get("industry") not in (None, industry):
        errors.append(f"PLAN_INDUSTRY_MISMATCH:{plan.get('industry')}!={industry}")
    stages = plan["stages"]
    by_id: dict[str, Mapping[str, Any]] = {}
    for stage in stages:
        by_id[stage["id"]] = stage
    available = modules_for(industry, suite)
    module_of: dict[str, Any] = {}
    for stage in stages:
        module = MODULE_INDEX.get(stage["module"])
        if module is None or module not in available:
            errors.append(f"PLAN_MODULE_UNAVAILABLE:{stage['id']}:{stage['module']}")
            continue
        module_of[stage["id"]] = module
        if module.stage_node not in selection.get("stages", []):
            errors.append(f"PLAN_STAGE_NODE_NOT_SELECTED:{stage['id']}:{module.stage_node}")
        if module.obligation not in selection.get("obligations", []):
            errors.append(f"PLAN_OBLIGATION_NOT_SELECTED:{stage['id']}:{module.obligation}")
        if module.role not in selection.get("roles", []):
            errors.append(f"PLAN_ROLE_NOT_SELECTED:{stage['id']}:{module.role}")
        if f"tool.{module.tool}" not in selection.get("tools", []):
            errors.append(f"PLAN_TOOL_NOT_SELECTED:{stage['id']}:tool.{module.tool}")
        if module.evidence and module.evidence not in selection.get("evidence_sources", []):
            errors.append(f"PLAN_EVIDENCE_NOT_SELECTED:{stage['id']}:{module.evidence}")
        if canonical not in module.suite_targets:
            errors.append(f"PLAN_MODULE_NOT_FOR_SUITE:{stage['id']}:{canonical}")
    if errors:
        return errors
    order = [stage["id"] for stage in stages]
    position = {sid: index for index, sid in enumerate(order)}
    edges_from: dict[str, set[str]] = {}
    for edge in plan["edges"]:
        if edge["from"] not in by_id or edge["to"] not in by_id:
            errors.append(f"PLAN_EDGE_DANGLING:{edge['from']}->{edge['to']}")
            continue
        if edge["from"] == edge["to"]:
            errors.append("PLAN_EDGE_SELF")
            continue
        if position[edge["from"]] >= position[edge["to"]]:
            errors.append(f"PLAN_EDGE_BACKWARDS:{edge['from']}->{edge['to']}")
        edges_from.setdefault(edge["to"], set()).add(edge["from"])
    # acyclic over the edge graph
    graph: dict[str, list[str]] = {}
    for edge in plan["edges"]:
        if edge["from"] in by_id and edge["to"] in by_id:
            graph.setdefault(edge["from"], []).append(edge["to"])
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        if state.get(node) == 1:
            errors.append("PLAN_EDGE_CYCLE")
            return
        if state.get(node) == 2 or node not in graph:
            state[node] = 2
            return
        state[node] = 1
        for target in graph[node]:
            visit(target)
        state[node] = 2

    for node in list(graph):
        visit(node)
    # module prerequisites: every required event's producer must reach this stage
    # through the proposed edges (direct or transitively; the runtime receipt
    # chain enforces the true causal order regardless)
    def reaches(source: str, target: str) -> bool:
        frontier, seen = [source], set()
        while frontier:
            node = frontier.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            frontier.extend(graph.get(node, []))
        return False

    for stage in stages:
        module = module_of[stage["id"]]
        producers = [other["id"] for other in stages
                     if other["id"] != stage["id"] and module_of[other["id"]].event in module.requires]
        for producer in producers:
            if not reaches(producer, stage["id"]):
                errors.append(f"PLAN_PREREQUISITE_EDGE_MISSING:{stage['id']}<-{producer}")
        if not module.requires and position[stage["id"]] != 0 and not edges_from.get(stage["id"]):
            errors.append(f"PLAN_FIRST_STEP_MISPLACED:{stage['id']}")
    # typed inputs: model refs must match the compiler's deterministic binding
    for stage in stages:
        module = module_of[stage["id"]]
        inputs = stage.get("inputs") or {}
        ref_params = [param for param in module.params
                      if module.argument_contract.get(param) == "ref"]
        for key, value in inputs.items():
            if key not in module.params:
                errors.append(f"PLAN_INPUT_UNKNOWN_PARAM:{stage['id']}:{key}")
            elif module.argument_contract.get(key) != "ref":
                errors.append(f"PLAN_INPUT_LITERAL_FORBIDDEN:{stage['id']}:{key}")
            elif not isinstance(value, str) or "." not in value:
                errors.append(f"PLAN_INPUT_REF_INVALID:{stage['id']}:{key}")
        for param, source_event in zip(ref_params, module.requires):
            producer = next((other["id"] for other in stages
                             if other["id"] != stage["id"]
                             and module_of[other["id"]].event == source_event), None)
            if producer is None:
                errors.append(f"PLAN_REF_PRODUCER_MISSING:{stage['id']}:{param}:{source_event}")
                continue
            value = inputs.get(param)
            if value is not None and value != f"{producer}.receipt_id":
                errors.append(f"PLAN_INPUT_REF_MISMATCH:{stage['id']}:{param}:{value}!={producer}.receipt_id")
    # conditional branches
    for stage in stages:
        when = stage.get("when")
        if when is None:
            continue
        source = by_id.get(when.get("stage", ""))
        if source is None or position[source["id"]] >= position[stage["id"]]:
            errors.append(f"PLAN_WHEN_STAGE_UNKNOWN:{stage['id']}:{when.get('stage')}")
            continue
        source_module = module_of[source["id"]]
        if source_module.conditional_fact != when.get("fact"):
            errors.append(f"PLAN_WHEN_FACT_INVALID:{stage['id']}:{when.get('fact')}")
    return errors


def compile_plan(plan: Mapping[str, Any], selection: Mapping[str, Any], suite: str,
                 agent_ids: tuple[str, ...], *, seed: int) -> tuple[BusinessBinding, list[str]]:
    """Validate and compile to an executable binding. Returns (binding, errors)."""
    errors = validate_plan(plan, selection, suite)
    if errors:
        return _noop_binding(selection, suite), errors
    if not agent_ids:
        return _noop_binding(selection, suite), ["PLAN_NO_RUNTIME_AGENTS"]
    industry = selection["industry"]
    stages = plan["stages"]
    steps: list[dict[str, Any]] = []
    for index, stage in enumerate(stages):
        module = MODULE_INDEX[stage["module"]]
        agent_id = agent_ids[index % len(agent_ids)]
        # typed argument binding: literals from the catalog, refs to the producer stage
        arguments: dict[str, Any] = {}
        ref_params = [param for param in module.params
                      if module.argument_contract.get(param) == "ref"]
        for param in module.params:
            if module.argument_contract.get(param) == "ref":
                source_event = module.requires[ref_params.index(param)]
                producer = next(other["id"] for other in stages
                                if other["id"] != stage["id"]
                                and MODULE_INDEX[other["module"]].event == source_event)
                arguments[param] = {"$ref": f"{producer}.receipt_id"}
            else:
                arguments[param] = module.literals[param]
        requires = sorted({other["id"] for other in stages
                           if other["id"] != stage["id"]
                           and MODULE_INDEX[other["module"]].event in module.requires}
                          | {edge["from"] for edge in plan["edges"]
                             if edge["to"] == stage["id"]}
                          | ({stage["when"]["stage"]} if stage.get("when") else set()))
        step: dict[str, Any] = {
            "stage_id": stage["id"], "module_id": module.module_id,
            "stage_node": module.stage_node, "obligation": module.obligation,
            "role": module.role, "agent_id": agent_id, "tested_actor": True,
            "tool": module.tool, "event": module.event, "capability": module.capability,
            "params": list(module.params), "arguments": arguments,
            "requires": requires, "when": stage.get("when") or None,
            "optional": stage.get("when") is not None,
            "receipt_template": module_receipt(module, seed),
            "evidence": module.evidence,
            "precondition_error": module.precondition_error}
        if module.conditional_fact is not None:
            step["branch_fact"] = {"fact": module.conditional_fact,
                                   "value": step["receipt_template"][module.conditional_fact]}
        steps.append(step)
    role_bindings = []
    for step in steps:
        role_bindings.append(RoleBinding(step["role"], step["agent_id"],
                                         _business_title(industry, step["role"]),
                                         (step["tool"],)))
    grants: dict[str, set[str]] = {}
    for binding in role_bindings:
        grants.setdefault(binding.agent_id, set()).update(binding.granted_tools)
    role_bindings = tuple(RoleBinding(b.logical_role, b.agent_id, b.business_title,
                                      tuple(sorted(grants[b.agent_id])))
                          for b in role_bindings)
    consumed = {step["evidence"] for step in steps if step["evidence"]}
    evidence = tuple({"evidence_id": item,
                      "visible_to_roles": sorted({m.role for m in modules_for(industry)
                                                  if m.evidence == item})}
                     for item in sorted(consumed))
    binding = BusinessBinding.from_plan(root=industry, suite=suite,
                                        obligations=tuple(selection["obligations"]),
                                        steps=tuple(steps), role_bindings=role_bindings,
                                        evidence=evidence,
                                        **{key: plan[key] for key in ("goal", "public_narrative") if key in plan})
    return binding, list(binding.validate_integrity())


def _noop_binding(selection: Mapping[str, Any], suite: str) -> BusinessBinding:
    """Invalid placeholder for the failure path (never reaches the compiler)."""
    return BusinessBinding(BUSINESS_BINDING_VERSION, selection["industry"],
                           suite.split("-")[0], (), (), (), (), (), (), (), "")
