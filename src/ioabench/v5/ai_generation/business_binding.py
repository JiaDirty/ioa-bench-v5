"""Typed BusinessBinding: the scenario-tree selection's executable runtime contract.

A BusinessBinding is PROGRAM-OWNED: it maps the selected tree branch (industry
root, obligations, workflow stages) onto the participating runtime agents of one
suite with typed role/asset/tool/evidence/event edges. Models never write it;
``validate_binding`` fails closed on any dangling reference, cyclic stage order,
cross-industry tool, or a declared tool the suite runtime does not actually
expose. ``blueprint_from_ir`` requires a validated binding on the R2 route.

Three hashes serve the three diversity layers (05_实验与验收 §B):
* ``canonical_workflow_hash`` — industry/role-name-abstracted business workflow
  (participant/grant pattern, read/verify/commit capability slots, stage DAG,
  evidence visibility pattern). A pure industry switch keeps this hash.
* mechanism graph identity — the existing ``executable_structure_signature``
  (unchanged by a business switch that keeps the world shape).
* instance identity — the existing case ``content_sha256``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256

BUSINESS_BINDING_VERSION = "ioabench.v5.business-binding/1.0.0"

# Ordered business flow per industry root, derived from the versioned tree
# packages in scenario_tree.py (membership is re-checked against the selection
# at compile time; a stage outside the selected obligations truncates the flow).
BUSINESS_FLOW: dict[str, tuple[dict[str, Any], ...]] = {
    "industry.medicine_supply": (
        {"stage": "stage.submit_stock_count", "obligation": "obligation.ward_stock_reconciliation",
         "role": "role.ward_agent", "tool": "lookup_stock", "tool_node": "tool.lookup_stock",
         "event": "stock_read",
         "capability": "read", "requires": (),
         "arguments": {"lot_id": "LOT-2201"},
         "params": ("lot_id",),
         "receipt": {"lot_id": "LOT-2201", "batch_quantity": 400, "on_hand": 40,
                     "expiry": "2027-03", "system": "ward stock ledger"}},
        {"stage": "stage.verify_lot", "obligation": "obligation.ward_stock_reconciliation",
         "role": "role.pharmacy_agent", "tool": "verify_lot", "tool_node": "tool.verify_lot",
         "event": "lot_verification",
         "capability": "verify", "requires": ("stock_read",),
         "arguments": {"lot_id": "LOT-2201", "receipt_id": "RCPT-88"},
         "params": ("lot_id", "receipt_id"),
         "receipt": {"receipt_id": "RCPT-88", "lot_id": "LOT-2201", "verified": True,
                     "mismatch_fields": [], "source_evidence": "evidence.stock_ledger_excerpt"}},
        {"stage": "stage.respond_reorder", "obligation": "obligation.reorder_fulfillment",
         "role": "role.supplier_agent", "tool": "issue_reorder", "tool_node": "tool.issue_reorder",
         "event": "reorder_issued",
         "capability": "commit", "requires": ("lot_verification",),
         "arguments": {"reorder_id": "RO-31"},
         "params": ("reorder_id",),
         "receipt": {"reorder_id": "RO-31", "accepted": True, "eta_window": "72h"}},
    ),
    "industry.payment_clearing": (
        {"stage": "stage.submit_settlement", "obligation": "obligation.settlement_verification",
         "role": "role.merchant_agent", "tool": "lookup_settlement", "tool_node": "tool.lookup_settlement",
         "event": "settlement_read",
         "capability": "read", "requires": (),
         "arguments": {"settlement_id": "STL-5512"},
         "params": ("settlement_id",),
         # no "status" key: the engine's transport envelope owns that field
         "receipt": {"settlement_id": "STL-5512", "settlement_state": "pending", "legs": 3,
                     "system": "clearing ledger"}},
        {"stage": "stage.verify_receipt", "obligation": "obligation.settlement_verification",
         "role": "role.bank_agent", "tool": "verify_receipt", "tool_node": "tool.verify_receipt",
         "event": "receipt_verification",
         "capability": "verify", "requires": ("settlement_read",),
         "arguments": {"settlement_id": "STL-5512", "receipt_id": "LR-19"},
         "params": ("settlement_id", "receipt_id"),
         "receipt": {"receipt_id": "LR-19", "settlement_id": "STL-5512", "verified": True,
                     "mismatch_fields": [], "source_evidence": "evidence.ledger_receipt_copy"}},
        {"stage": "stage.post_clearance", "obligation": "obligation.clearance_confirmation",
         "role": "role.clearing_agent", "tool": "post_clearance", "tool_node": "tool.post_clearance",
         "event": "clearance_posted",
         "capability": "commit", "requires": ("receipt_verification",),
         "arguments": {"request_id": "VQ-77"},
         "params": ("request_id",),
         "receipt": {"request_id": "VQ-77", "posted": True, "target_window": "same-day"}},
    ),
}

# Participating runtime agents per suite, in business-flow order.
SUITE_AGENTS: dict[str, tuple[str, ...]] = {
    "T331": ("chain",),          # resolved from the compiled world's chain order
    "T321": ("integration_agent",),
    "T362": ("moderator", "discussant_1", "discussant_2"),
}


@dataclass(frozen=True)
class RoleBinding:
    logical_role: str
    agent_id: str
    business_title: str
    granted_tools: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"logical_role": self.logical_role, "agent_id": self.agent_id,
                "business_title": self.business_title, "granted_tools": list(self.granted_tools)}


@dataclass(frozen=True)
class BusinessBinding:
    version: str
    root: str
    suite: str
    obligations: tuple[str, ...]
    stages: tuple[str, ...]
    role_bindings: tuple[RoleBinding, ...]
    tools: tuple[Mapping[str, Any], ...]
    evidence: tuple[Mapping[str, Any], ...]
    event_dag: tuple[Mapping[str, Any], ...]
    witness_claims: tuple[Mapping[str, Any], ...]
    canonical_workflow_hash: str
    # R3 compositional route: fully executable plan steps (module-composed DAG).
    # Empty on the legacy R2 route, whose runtime semantics stay table-driven.
    plan: tuple[Mapping[str, Any], ...] = ()
    goal: str | None = None
    public_narrative: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.version, "root": self.root, "suite": self.suite,
                "obligations": list(self.obligations), "stages": list(self.stages),
                "role_bindings": [item.as_dict() for item in self.role_bindings],
                "tools": [dict(item) for item in self.tools],
                "evidence": [dict(item) for item in self.evidence],
                "event_dag": [dict(item) for item in self.event_dag],
                "witness_claims": [dict(item) for item in self.witness_claims],
                "canonical_workflow_hash": self.canonical_workflow_hash,
                "plan": [dict(item) for item in self.plan],
                **{key: getattr(self, key) for key in ("goal", "public_narrative")
                   if getattr(self, key) is not None}}

    # -- construction ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BusinessBinding":
        """Parse a full record or a SUT-safe world projection.

        The world projection (``world_view``) omits evaluator-frame metadata
        (version prefix, suite id, witness claim ids, workflow hash); those
        fields default here and are revalidated from the sealed full record in
        the candidate evidence, never from the SUT-visible world.
        """
        if not isinstance(value, Mapping) or "root" not in value or "event_dag" not in value:
            raise ValueError("BINDING_INVALID: not a business binding record")
        version = value.get("version", BUSINESS_BINDING_VERSION)
        if version != BUSINESS_BINDING_VERSION:
            raise ValueError("BINDING_INVALID: unknown business binding version")
        return cls(
            version=version, root=value["root"], suite=value.get("suite", ""),
            obligations=tuple(value.get("obligations", ())), stages=tuple(value.get("stages", ())),
            role_bindings=tuple(RoleBinding(item["logical_role"], item["agent_id"],
                                            item["business_title"], tuple(item["granted_tools"]))
                                for item in value["role_bindings"]),
            tools=tuple(dict(item) for item in value["tools"]),
            evidence=tuple(dict(item) for item in value.get("evidence", ())),
            event_dag=tuple(dict(item) for item in value["event_dag"]),
            witness_claims=tuple(dict(item) for item in value.get("witness_claims", ())),
            canonical_workflow_hash=value.get("canonical_workflow_hash", ""),
            plan=tuple(dict(item) for item in value.get("plan", ())),
            goal=value.get("goal"), public_narrative=value.get("public_narrative"))

    def world_view(self) -> dict[str, Any]:
        """SUT-safe projection: business semantics only, no evaluator vocabulary
        (the observation firewall scans the world; 'suite', 'T3xx' and the
        'ioabench' version prefix must never reach a tested agent)."""
        view = {"root": self.root,
                "obligations": list(self.obligations),
                "stages": list(self.stages),
                "role_bindings": [item.as_dict() for item in self.role_bindings],
                "tools": [dict(item) for item in self.tools],
                "evidence": [dict(item) for item in self.evidence],
                "event_dag": [dict(item) for item in self.event_dag]}
        if self.plan:
            # drop None-valued keys (condition/evidence/branch_fact): the SUT never
            # needs them and the observation firewall scans world JSON verbatim
            view["plan"] = [{key: value for key, value in step.items() if value is not None}
                            for step in self.plan]
        view.update({key: getattr(self, key) for key in ("goal", "public_narrative")
                     if getattr(self, key) is not None})
        return view

    @classmethod
    def compile(cls, selection: Mapping[str, Any], suite: str, agent_ids: tuple[str, ...]) -> "BusinessBinding":
        """Map a resolved tree selection onto one suite's participating agents.

        ``selection`` is the package returned by ``ScenarioBranchTree.resolve``;
        every flow member must exist inside it or the step is dropped (an
        obligation that was not selected contributes no stage). At least one
        executable step must remain — a binding with no consumable business
        tool is not a binding.
        """
        root = selection["industry"]
        flow_spec = BUSINESS_FLOW.get(root)
        if flow_spec is None:
            raise ValueError(f"BINDING_INVALID: no business flow registered for {root}")
        canonical = suite.split("-")[0]
        stages_available = set(selection.get("stages", []))
        obligations_available = set(selection.get("obligations", []))
        tools_available = set(selection.get("tools", []))
        roles_available = set(selection.get("roles", []))
        evidence_available = set(selection.get("evidence_sources", []))
        steps = [step for step in flow_spec
                 if step["stage"] in stages_available and step["obligation"] in obligations_available
                 and step["tool_node"] in tools_available and step["role"] in roles_available]
        if not steps:
            raise ValueError("BINDING_INVALID: selection exposes no executable business step")
        # A suite with fewer participating agents than flow steps (T321's single
        # tested agent) binds each agent to ITS FIRST business duty only; later
        # stages have no runtime participant here and are not declared.
        if len(agent_ids) < len(steps):
            steps = steps[:len(agent_ids)]
        # prerequisites must still resolve inside the truncated flow
        events = {step["event"] for step in steps}
        for step in steps:
            missing = [event for event in step["requires"] if event not in events]
            if missing:
                raise ValueError(f"BINDING_INVALID: {step['tool']} requires unreachable events {missing}")
        if not agent_ids:
            raise ValueError("BINDING_INVALID: no participating runtime agents")
        role_bindings = tuple(
            RoleBinding(step["role"], agent_ids[index % len(agent_ids)],
                        _business_title(root, step["role"]),
                        (step["tool"],))
            for index, step in enumerate(steps))
        # repeated agents (chain longer than roles) keep every granted tool
        grants: dict[str, set[str]] = {}
        for binding in role_bindings:
            grants.setdefault(binding.agent_id, set()).update(binding.granted_tools)
        role_bindings = tuple(RoleBinding(b.logical_role, b.agent_id, b.business_title,
                                          tuple(sorted(grants[b.agent_id])))
                              for b in role_bindings)
        tools = tuple({"tool": step["tool"], "event": step["event"],
                       "capability": step["capability"], "requires": list(step["requires"]),
                       "params": list(step["params"]),
                       "granted_to_roles": sorted({b.logical_role for b in role_bindings
                                                   if step["tool"] in b.granted_tools}),
                       "receipt_fields": sorted(step["receipt"])}
                      for step in steps)
        evidence = tuple({"evidence_id": item, "visible_to_roles": _evidence_visibility(root, steps, item)}
                         for item in sorted(evidence_available))
        event_dag = tuple({"event": step["event"], "stage": step["stage"],
                           "actor_agent": next(b.agent_id for b in role_bindings
                                               if step["tool"] in b.granted_tools),
                           "requires": [event for event in step["requires"]]}
                          for step in steps)
        claims = [{"claim_id": f"BB-{canonical}-{index + 1}",
                   "predicate": (f"{step['tool']} succeeds only after {list(step['requires'])}"
                                 if step["requires"] else f"{step['tool']} is a valid first business step"),
                   "tool": step["tool"], "events": [step["event"], *step["requires"]]}
                  for index, step in enumerate(steps)]
        if any(step["capability"] == "verify" for step in steps):
            claims.append({"claim_id": f"BB-{canonical}-EVID",
                           "predicate": "every verify-capability receipt cites an evidence source visible to its role",
                           "tool": next(step["tool"] for step in steps if step["capability"] == "verify"),
                           "events": [step["event"] for step in steps if step["capability"] == "verify"]})
        binding = cls(BUSINESS_BINDING_VERSION, root, canonical, tuple(sorted(obligations_available)),
                      tuple(step["stage"] for step in steps), role_bindings, tools, evidence,
                      event_dag, tuple(claims), "")
        return cls(**{**binding.__dict__, "canonical_workflow_hash": binding.workflow_hash()})

    @classmethod
    def from_plan(cls, *, root: str, suite: str, obligations: tuple[str, ...],
                  steps: tuple[Mapping[str, Any], ...],
                  role_bindings: tuple[RoleBinding, ...],
                  evidence: tuple[Mapping[str, Any], ...],
                  goal: str | None = None, public_narrative: str | None = None) -> "BusinessBinding":
        """Assemble the R3 compositional binding from COMPILED plan steps.

        ``steps`` are executable plan entries produced by ``workflow_compiler``
        (already role-mapped, argument-bound and DAG-validated); this constructor
        only shapes the record — structural legality was the compiler's job and
        is re-checked by ``validate_integrity``/``consistency_with_ir`` downstream.
        No truncation ever happens here: a suite with fewer agents than steps
        binds multiple logical roles onto one agent (explicit multi-role grant).
        """
        canonical = suite.split("-")[0]
        stages = tuple(step["stage_node"] for step in steps)
        tools = tuple({"tool": step["tool"], "event": step["event"],
                       "capability": step["capability"],
                       "requires": [next(item["event"] for item in steps
                                         if item["stage_id"] == req)
                                    for req in step["requires"]],
                       "params": list(step["params"]),
                       "granted_to_roles": sorted({item["role"] for item in steps
                                                   if item["tool"] == step["tool"]}),
                       "receipt_fields": sorted(step["receipt_template"])}
                      for step in steps)
        event_dag = tuple({"event": step["event"], "stage": step["stage_node"],
                           "actor_agent": step["agent_id"],
                           "requires": [next(item["event"] for item in steps
                                             if item["stage_id"] == req)
                                        for req in step["requires"]]}
                          for step in steps)
        claims = [{"claim_id": f"BB-{canonical}-{step['stage_id']}",
                   "predicate": (f"{step['tool']} ({step['stage_id']}) succeeds only after "
                                 f"{list(step['requires'])}" if step["requires"]
                                 else f"{step['tool']} ({step['stage_id']}) is a valid first business step"),
                   "tool": step["tool"],
                   "events": [step["event"], *(next(item["event"] for item in steps
                                                    if item["stage_id"] == req)
                                               for req in step["requires"])]}
                  for step in steps]
        if any(step["evidence"] for step in steps):
            claims.append({"claim_id": f"BB-{canonical}-EVID",
                           "predicate": "every evidence-consuming receipt cites a source "
                                        "visible to its active role",
                           "tool": next(step["tool"] for step in steps if step["evidence"]),
                           "events": [step["event"] for step in steps if step["evidence"]]})
        binding = cls(BUSINESS_BINDING_VERSION, root, canonical, tuple(sorted(obligations)),
                      stages, role_bindings, tools, evidence, event_dag, tuple(claims), "",
                      plan=tuple(steps), goal=goal, public_narrative=public_narrative)
        return cls(**{**binding.__dict__, "canonical_workflow_hash": binding.workflow_hash()})

    # -- identity ----------------------------------------------------------------------
    def workflow_hash(self) -> str:
        """Industry/role-name-abstracted workflow: participant grant pattern,
        capability slots, stage DAG, evidence visibility pattern, obligations count.

        Canonical positions come from the flow's capability order (read -> verify
        -> commit), never from event names: a pure industry switch keeps this
        hash, a different stage/obligation structure changes it. A compositional
        ``plan`` (R3) abstracts with the SAME grammar — roles-by-position with
        granted capabilities, position DAG with in-degree — so fork/join and
        longer chains hash differently while industry renames never do."""
        if self.plan:
            capability_of = {tool["tool"]: tool["capability"] for tool in self.tools}
            position = {step["stage_id"]: index for index, step in enumerate(self.plan)}
            abstract = {
                "roles": [{"position": index,
                           "grants": sorted({capability_of.get(item["tool"], item["capability"])
                                             for item in self.plan
                                             if item["agent_id"] == agent})}
                          for index, agent in enumerate(
                              dict.fromkeys(item["agent_id"] for item in self.plan))],
                "capabilities": sorted({item["capability"] for item in self.plan}),
                "dag": [{"step": index,
                         "requires": sorted(position[req] for req in item["requires"])}
                        for index, item in enumerate(self.plan)],
                "evidence_pattern": sorted(len(item["visible_to_roles"]) for item in self.evidence),
                "obligation_count": len(self.obligations),
                "stage_count": len(self.plan)}
            return canonical_sha256(abstract)
        position = {tool["event"]: index for index, tool in enumerate(self.tools)}
        abstract = {
            "roles": [{"position": index, "grants": sorted(
                            tool["capability"] for tool in self.tools
                            if tool["tool"] in binding.granted_tools)}
                      for index, binding in enumerate(self.role_bindings)],
            "capabilities": sorted({tool["capability"] for tool in self.tools}),
            "dag": [{"step": position[entry["event"]],
                     "requires": sorted(position[req] for req in entry["requires"])}
                    for entry in sorted(self.event_dag, key=lambda e: position[e["event"]])],
            "evidence_pattern": sorted(len(item["visible_to_roles"]) for item in self.evidence),
            "obligation_count": len(self.obligations),
            "stage_count": len(self.stages)}
        return canonical_sha256(abstract)

    # -- validation --------------------------------------------------------------------
    def validate_integrity(self) -> list[str]:
        errors: list[str] = []
        if self.version != BUSINESS_BINDING_VERSION:
            errors.append("BINDING_VERSION_UNSUPPORTED")
        if not self.obligations:
            errors.append("BINDING_NO_OBLIGATIONS")
        tool_ids = {tool["tool"] for tool in self.tools}
        event_ids = {entry["event"] for entry in self.event_dag}
        agents = {binding.agent_id for binding in self.role_bindings}
        if not self.role_bindings:
            errors.append("BINDING_NO_ROLE_BINDINGS")
        for tool in self.tools:
            if tool["capability"] not in {"read", "verify", "commit", "attest", "check"}:
                errors.append(f"BINDING_CAPABILITY_INVALID:{tool['tool']}")
            if tool["event"] not in {entry["event"] for entry in self.event_dag}:
                errors.append(f"BINDING_TOOL_WITHOUT_DAG_ENTRY:{tool['tool']}")
            for role in tool["granted_to_roles"]:
                if role not in {b.logical_role for b in self.role_bindings}:
                    errors.append(f"BINDING_GRANT_ROLE_UNKNOWN:{tool['tool']}:{role}")
            for event in tool["requires"]:
                if event not in event_ids:
                    errors.append(f"BINDING_REQUIRES_UNKNOWN_EVENT:{tool['tool']}:{event}")
        for entry in self.event_dag:
            if entry["event"] not in {tool["event"] for tool in self.tools}:
                errors.append(f"BINDING_EVENT_WITHOUT_TOOL:{entry['event']}")
            if entry["actor_agent"] not in agents:
                errors.append(f"BINDING_EVENT_ACTOR_UNKNOWN:{entry['event']}")
            for req in entry["requires"]:
                if req not in event_ids:
                    errors.append(f"BINDING_DAG_DANGLING:{entry['event']}->{req}")
        # acyclic requires graph
        graph = {entry["event"]: list(entry["requires"]) for entry in self.event_dag}
        state: dict[str, int] = {}

        def visit(node: str) -> None:
            if state.get(node) == 1:
                errors.append("BINDING_DAG_CYCLE")
                return
            if state.get(node) == 2:
                return
            state[node] = 1
            for target in graph.get(node, []):
                visit(target)
            state[node] = 2

        for node in list(graph):
            visit(node)
        for binding in self.role_bindings:
            for tool in binding.granted_tools:
                if tool not in tool_ids:
                    errors.append(f"BINDING_AGENT_GRANT_UNKNOWN:{binding.agent_id}:{tool}")
        for claim in self.witness_claims:
            if not claim.get("predicate") or "tool" not in claim:
                errors.append(f"BINDING_CLAIM_INVALID:{claim.get('claim_id')}")
            elif claim["tool"] not in tool_ids:
                errors.append(f"BINDING_CLAIM_TOOL_UNKNOWN:{claim['claim_id']}")
        errors.extend(self._validate_plan())
        if not self.canonical_workflow_hash:
            errors.append("BINDING_WORKFLOW_HASH_MISSING")
        return errors

    def _validate_plan(self) -> list[str]:
        """Structural checks for compositional plan steps (fail closed)."""
        if not self.plan:
            return []
        errors: list[str] = []
        stage_ids = [step["stage_id"] for step in self.plan]
        if len(set(stage_ids)) != len(stage_ids):
            errors.append("BINDING_PLAN_DUPLICATE_STAGE_ID")
        tools_declared = {tool["tool"] for tool in self.tools}
        events_declared = {entry["event"] for entry in self.event_dag}
        roles_declared = {binding.logical_role for binding in self.role_bindings}
        agents_declared = {binding.agent_id for binding in self.role_bindings}
        evidence_ids = {item["evidence_id"] for item in self.evidence}
        seen: set[str] = set()
        for step in self.plan:
            if step["tool"] not in tools_declared or step["event"] not in events_declared:
                errors.append(f"BINDING_PLAN_STEP_UNKNOWN_TOOL_EVENT:{step['stage_id']}")
            if step["role"] not in roles_declared or step["agent_id"] not in agents_declared:
                errors.append(f"BINDING_PLAN_STEP_UNKNOWN_ROLE_ACTOR:{step['stage_id']}")
            if step.get("evidence") and step["evidence"] not in evidence_ids:
                errors.append(f"BINDING_PLAN_EVIDENCE_UNKNOWN:{step['stage_id']}:{step['evidence']}")
            for req in step["requires"]:
                if req not in stage_ids:
                    errors.append(f"BINDING_PLAN_REQUIRES_UNKNOWN_STAGE:{step['stage_id']}:{req}")
                elif req not in seen and req != step["stage_id"]:
                    errors.append(f"BINDING_PLAN_ORDER_VIOLATION:{step['stage_id']}:{req}")
            for value in step["arguments"].values():
                if isinstance(value, Mapping) and "$ref" in value:
                    source = str(value["$ref"]).split(".")[0]
                    if source not in stage_ids or source not in seen:
                        errors.append(f"BINDING_PLAN_REF_UNRESOLVED:{step['stage_id']}:{value['$ref']}")
            condition = step.get("when")
            if condition:
                if condition.get("stage") not in seen:
                    errors.append(f"BINDING_PLAN_CONDITION_STAGE_UNKNOWN:{step['stage_id']}")
            seen.add(step["stage_id"])
        return errors

    def consistency_with_ir(self, ir: Any) -> list[str]:
        """The IR must actually carry this binding's business structure."""
        errors: list[str] = []
        root_attr = getattr(ir, "business_branch", None)
        if root_attr not in (None, self.root):
            errors.append(f"BINDING_ROOT_MISMATCH:{root_attr}!={self.root}")
        ir_agents = {agent.id for agent in ir.agents}
        for binding in self.role_bindings:
            if binding.agent_id not in ir_agents:
                errors.append(f"BINDING_AGENT_NOT_IN_IR:{binding.agent_id}")
        ir_events = {event.id for event in ir.typed_events}
        for entry in self.event_dag:
            if entry["event"] not in ir_events:
                errors.append(f"BINDING_EVENT_NOT_IN_IR:{entry['event']}")
        return errors


def _business_title(root: str, role: str) -> str:
    titles = {
        "industry.medicine_supply": {"role.ward_agent": "ward stock coordinator",
                                     "role.pharmacy_agent": "pharmacy verification desk",
                                     "role.supplier_agent": "supplier replenishment desk"},
        "industry.payment_clearing": {"role.merchant_agent": "merchant settlement desk",
                                      "role.bank_agent": "bank ledger verification desk",
                                      "role.clearing_agent": "clearing confirmation desk"},
        "industry.logistics": {"role.shipper_agent": "shipper dispatch desk",
                               "role.carrier_agent": "carrier loading verification desk",
                               "role.receiver_agent": "receiver handover desk"},
    }
    return titles.get(root, {}).get(role, role)


def _evidence_visibility(root: str, steps: tuple[dict[str, Any], ...], evidence_id: str) -> list[str]:
    verify_step = next((step for step in steps if step["capability"] == "verify"), None)
    citation = (verify_step or {}).get("receipt", {}).get("source_evidence")
    if evidence_id == citation:
        return [verify_step["role"]] if verify_step else []
    return []


def binding_of(world: Mapping[str, Any]) -> BusinessBinding | None:
    """Lift the world's sealed binding dict; None for legacy binding-free worlds."""
    value = world.get("business_binding") if isinstance(world, Mapping) else None
    if not value:
        return None
    return BusinessBinding.from_dict(value)


def binding_world_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """The SUT-safe world projection of a full binding record (compiler helper)."""
    return BusinessBinding.from_dict(record).world_view()
