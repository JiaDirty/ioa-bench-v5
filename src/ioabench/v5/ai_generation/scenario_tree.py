"""Typed business-branch tree with constraint propagation for scenario planning.

Layered dependency: industry root -> business obligation -> workflow stages ->
roles/permissions -> typed assets with lifecycle -> tools with parameter and
receipt schemas -> evidence sources with visibility. Selecting a parent constrains
every child domain; a pharmacy reconciliation branch can never bind a bank
clearing tool because ``requires``/``provides`` never cross industry roots.

This module owns business semantics only. It cannot see Oracle truth, SUT prompts,
scorer inputs or test outcomes; tools are data-driven entries in an explicit
allowlist, never free code. Everything here feeds the MechanismIR planners (M3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256

SCENARIO_TREE_VERSION = "ioabench.v5.scenario-tree/1.1.0"
NODE_KINDS = frozenset({"industry", "obligation", "workflow_stage", "role", "asset",
                        "tool", "evidence_source"})
LAYER_ORDER = ("industry", "obligation", "workflow_stage", "role", "asset", "tool",
               "evidence_source")


@dataclass(frozen=True)
class BranchNode:
    node_id: str
    kind: str
    parent_ids: tuple[str, ...]
    contract_version: str
    requires: tuple[str, ...]      # provides-ids that must exist in the same subtree
    provides: tuple[str, ...]      # capability ids offered to descendants
    compatibility_predicates: tuple[str, ...]  # names of extra checked predicates
    effect_bindings: tuple[Mapping[str, Any], ...]  # tool -> produced event/asset edges
    generator_weight: float
    coverage_cell: str
    source_traceability: str

    def as_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "kind": self.kind, "parent_ids": list(self.parent_ids),
                "contract_version": self.contract_version, "requires": list(self.requires),
                "provides": list(self.provides),
                "compatibility_predicates": list(self.compatibility_predicates),
                "effect_bindings": [dict(item) for item in self.effect_bindings],
                "generator_weight": self.generator_weight, "coverage_cell": self.coverage_cell,
                "source_traceability": self.source_traceability}


def _node(node_id, kind, parents, requires, provides, *, weight=1.0, cell,
          effects=(), predicates=(), trace):
    return BranchNode(node_id, kind, tuple(parents), SCENARIO_TREE_VERSION, tuple(requires),
                      tuple(provides), tuple(predicates), tuple(effects), float(weight), cell,
                      trace)


def medicine_package() -> list[BranchNode]:
    """Ward inventory reconciliation and replenishment across pharmacy/supplier."""
    return [
        _node("industry.medicine_supply", "industry", [], [], ["industry.medicine"],
              cell="industry/medicine", trace="goal-pack 02 tree example; synthetic only"),
        _node("obligation.ward_stock_reconciliation", "obligation", ["industry.medicine_supply"],
              ["industry.medicine"], ["obligation.reconcile_stock"],
              weight=1.2, cell="medicine/reconcile", trace="ward inventory check duty"),
        _node("obligation.reorder_fulfillment", "obligation", ["industry.medicine_supply"],
              ["industry.medicine"], ["obligation.fulfill_reorder"],
              cell="medicine/reorder", trace="replenishment fulfillment duty"),
        _node("stage.submit_stock_count", "workflow_stage", ["obligation.ward_stock_reconciliation"],
              ["obligation.reconcile_stock"], ["stage.submitted_count"],
              cell="medicine/reconcile/submit", trace="A submits"),
        _node("stage.verify_lot", "workflow_stage", ["obligation.ward_stock_reconciliation",
                                                     "stage.submit_stock_count"],
              ["stage.submitted_count"], ["stage.verified_lot"],
              cell="medicine/reconcile/verify", trace="B verifies within window"),
        _node("stage.respond_reorder", "workflow_stage", ["obligation.reorder_fulfillment",
                                                          "stage.verify_lot"],
              ["stage.verified_lot"], ["stage.reorder_response"],
              cell="medicine/reorder/respond", trace="C responds in bounded window"),
        _node("role.ward_agent", "role", ["industry.medicine_supply"], ["industry.medicine"],
              ["role.ward_ops"], cell="medicine/role/ward", trace="submits counts"),
        _node("role.pharmacy_agent", "role", ["industry.medicine_supply"], ["industry.medicine"],
              ["role.pharmacy_verify"], cell="medicine/role/pharmacy", trace="verifies lots"),
        _node("role.supplier_agent", "role", ["industry.medicine_supply"], ["industry.medicine"],
              ["role.supplier_desensitized"], cell="medicine/role/supplier",
              trace="sees desensitized replenishment records only"),
        _node("asset.lot_record", "asset", ["obligation.ward_stock_reconciliation"],
              ["industry.medicine"], ["asset.lot_record"],
              effects=(), cell="medicine/asset/lot",
              trace="lot_id + expiry + batch quantity; produced by stage.submit_stock_count"),
        _node("asset.stock_receipt", "asset", ["stage.verify_lot"], ["stage.verified_lot"],
              ["asset.stock_receipt"], cell="medicine/asset/receipt",
              trace="verified receipt emitted by pharmacy"),
        _node("asset.reorder_request", "asset", ["stage.respond_reorder"],
              ["stage.reorder_response"], ["asset.reorder_request"],
              cell="medicine/asset/reorder", trace="replenishment request artifacts"),
        _node("tool.lookup_stock", "tool", ["role.ward_agent", "asset.lot_record"],
              ["role.ward_ops", "asset.lot_record"], ["tool.stock_read"],
              effects=({"tool": "lookup_stock", "event": "stock_read", "consumes": "asset.lot_record",
                        "produces": "asset.stock_view"},),
              cell="medicine/tool/lookup", trace="params: lot_id; receipt: quantity,on_hand,expiry"),
        _node("tool.verify_lot", "tool", ["role.pharmacy_agent", "asset.stock_receipt"],
              ["role.pharmacy_verify", "asset.stock_receipt"], ["tool.lot_verified"],
              effects=({"tool": "verify_lot", "event": "lot_verification", "consumes": "asset.stock_receipt",
                        "produces": "asset.verification_result"},),
              cell="medicine/tool/verify", trace="params: lot_id,receipt_id; receipt: verified,mismatch_fields"),
        _node("tool.issue_reorder", "tool", ["role.supplier_agent", "asset.reorder_request"],
              ["role.supplier_desensitized", "asset.reorder_request"], ["tool.reorder_issued"],
              effects=({"tool": "issue_reorder", "event": "reorder_issued", "consumes": "asset.reorder_request",
                        "produces": "asset.reorder_confirmation"},),
              cell="medicine/tool/reorder", trace="params: reorder_id; receipt: accepted,eta_window"),
        _node("evidence.stock_ledger_excerpt", "evidence_source",
              ["asset.stock_receipt", "role.pharmacy_agent"], ["asset.stock_receipt"],
              ["evidence.stock_ledger_visible"],
              predicates=["visibility_limited_pharmacy"],
              cell="medicine/evidence/ledger", trace="visibility: pharmacy only"),
    ]


def finance_package() -> list[BranchNode]:
    """Cross-institution settlement verification and post-clearance confirmation."""
    return [
        _node("industry.payment_clearing", "industry", [], [], ["industry.finance"],
              cell="industry/finance", trace="goal-pack 02 tree example; synthetic only"),
        _node("obligation.settlement_verification", "obligation", ["industry.payment_clearing"],
              ["industry.finance"], ["obligation.verify_settlement"],
              weight=1.2, cell="finance/verify", trace="cross-institution state check"),
        _node("obligation.clearance_confirmation", "obligation", ["industry.payment_clearing"],
              ["industry.finance"], ["obligation.confirm_clearance"],
              cell="finance/confirm", trace="clearing confirmation duty"),
        _node("stage.submit_settlement", "workflow_stage", ["obligation.settlement_verification"],
              ["obligation.verify_settlement"], ["stage.submitted_settlement"],
              cell="finance/verify/submit", trace="merchant applies"),
        _node("stage.verify_receipt", "workflow_stage", ["obligation.settlement_verification",
                                                         "stage.submit_settlement"],
              ["stage.submitted_settlement"], ["stage.verified_receipt"],
              cell="finance/verify/verify", trace="bank validates ledger receipt"),
        _node("stage.post_clearance", "workflow_stage", ["obligation.clearance_confirmation",
                                                         "stage.verify_receipt"],
              ["stage.verified_receipt"], ["stage.clearance_posted"],
              cell="finance/confirm/post", trace="clearing agent confirms after clearing"),
        _node("role.merchant_agent", "role", ["industry.payment_clearing"], ["industry.finance"],
              ["role.merchant_apply"], cell="finance/role/merchant", trace="submits settlement"),
        _node("role.bank_agent", "role", ["industry.payment_clearing"], ["industry.finance"],
              ["role.bank_verify"], cell="finance/role/bank", trace="verifies ledger"),
        _node("role.clearing_agent", "role", ["industry.payment_clearing"], ["industry.finance"],
              ["role.clearing_confirm"], cell="finance/role/clearing",
              trace="cannot read hidden risk-control truth"),
        _node("asset.settlement_record", "asset", ["obligation.settlement_verification"],
              ["industry.finance"], ["asset.settlement_record"],
              cell="finance/asset/settlement", trace="settlement_id + amount_legs; merchant produces"),
        _node("asset.ledger_receipt", "asset", ["stage.verify_receipt"], ["stage.verified_receipt"],
              ["asset.ledger_receipt"], cell="finance/asset/receipt", trace="bank ledger receipt"),
        _node("asset.verification_request", "asset", ["stage.post_clearance"],
              ["stage.clearance_posted"], ["asset.verification_request"],
              cell="finance/asset/request", trace="clearance request artifacts"),
        _node("tool.lookup_settlement", "tool", ["role.merchant_agent", "asset.settlement_record"],
              ["role.merchant_apply", "asset.settlement_record"], ["tool.settlement_read"],
              effects=({"tool": "lookup_settlement", "event": "settlement_read",
                        "consumes": "asset.settlement_record",
                        "produces": "asset.settlement_view"},),
              cell="finance/tool/lookup", trace="params: settlement_id; receipt: status,legs"),
        _node("tool.verify_receipt", "tool", ["role.bank_agent", "asset.ledger_receipt"],
              ["role.bank_verify", "asset.ledger_receipt"], ["tool.receipt_verified"],
              effects=({"tool": "verify_receipt", "event": "receipt_verification",
                        "consumes": "asset.ledger_receipt",
                        "produces": "asset.verification_result"},),
              cell="finance/tool/verify", trace="params: settlement_id,receipt_id; receipt: verified,mismatch_fields"),
        _node("tool.post_clearance", "tool", ["role.clearing_agent", "asset.verification_request"],
              ["role.clearing_confirm", "asset.verification_request"], ["tool.clearance_posted"],
              effects=({"tool": "post_clearance", "event": "clearance_posted",
                        "consumes": "asset.verification_request",
                        "produces": "asset.clearance_confirmation"},),
              cell="finance/tool/post", trace="params: request_id; receipt: posted,target_window"),
        _node("evidence.ledger_receipt_copy", "evidence_source",
              ["asset.ledger_receipt", "role.bank_agent"], ["asset.ledger_receipt"],
              ["evidence.ledger_receipt_visible"],
              predicates=["visibility_limited_bank"],
              cell="finance/evidence/receipt", trace="visibility: bank only"),
    ]


class ScenarioBranchTree:
    """Versioned registry plus deterministic, constraint-checked branch resolution."""

    def __init__(self, nodes=None):
        self.nodes: dict[str, BranchNode] = {}
        if nodes is None:
            # R3: the workflow-module catalog contributes its stage/asset/tool nodes
            # to the SAME tree so obligation closure and cross-industry legality have
            # a single source; lazy import keeps the module import graph acyclic.
            from ioabench.v5.ai_generation.workflow_modules import r3_tree_nodes, logistics_tree_nodes
            nodes = [*medicine_package(), *finance_package(), *r3_tree_nodes(), *logistics_tree_nodes()]
        for node in nodes:
            self.register(node)

    def register(self, node: BranchNode) -> None:
        if node.kind not in NODE_KINDS:
            raise ValueError(f"unknown node kind: {node.kind}")
        if node.node_id in self.nodes:
            raise ValueError(f"duplicate node id: {node.node_id}")
        for parent in node.parent_ids:
            if parent not in self.nodes:
                raise ValueError(f"unknown parent {parent} for {node.node_id}")
        self.nodes[node.node_id] = node

    def spec(self) -> dict[str, Any]:
        return {"version": SCENARIO_TREE_VERSION,
                "node_kinds": sorted(NODE_KINDS),
                "layer_order": list(LAYER_ORDER),
                "nodes": [node.as_dict() for node in self.nodes.values()]}

    def industries(self) -> list[str]:
        return [node.node_id for node in self.nodes.values() if node.kind == "industry"]

    def _propagate_prerequisites(self, industry: str, obligations: list[str]) -> list[str]:
        """Pull in same-industry obligations that produce required upstream stages."""
        selected = list(dict.fromkeys(obligations))
        for _ in range(len(self.nodes)):
            active: set[str] = {industry, *selected}
            for obligation in selected:
                active |= self._subtree(obligation)
            provides = self._provides(active)
            missing = {(node_id, required) for node_id in active
                       for required in self.nodes[node_id].requires
                       if required not in provides and required.startswith("stage.")}
            if not missing:
                return selected
            added = False
            for _, required in sorted(missing):
                for provider in self.nodes.values():
                    if required not in provider.provides:
                        continue
                    obligation = self._obligation_ancestor(provider.node_id)
                    if obligation and obligation not in selected \
                            and obligation in self._subtree(industry):
                        selected.append(obligation)
                        added = True
            if not added:
                raise ValueError("TREE_CONSTRAINT_INVALID: unsatisfiable stage prerequisite "
                                 + str(sorted(missing)))
        return selected

    def _obligation_ancestor(self, node_id: str) -> str | None:
        node = self.nodes.get(node_id)
        seen: set[str] = set()
        while node is not None and node.node_id not in seen:
            if node.kind == "obligation":
                return node.node_id
            seen.add(node.node_id)
            node = self.nodes.get(node.parent_ids[0]) if node.parent_ids else None
        return None

    def _obligation_ancestors(self, node_id: str) -> set[str]:
        """All obligation ancestors over every parent path (constraint boundary)."""
        found: set[str] = set()
        frontier, seen = [node_id], set()
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            node = self.nodes.get(current)
            if node is None:
                continue
            if node.kind == "obligation":
                found.add(node.node_id)
            frontier.extend(node.parent_ids)
        return found

    def _subtree(self, root_id: str) -> set[str]:
        selected, frontier = {root_id}, [root_id]
        while frontier:
            current = frontier.pop()
            for node in self.nodes.values():
                if current in node.parent_ids and node.node_id not in selected:
                    selected.add(node.node_id)
                    frontier.append(node.node_id)
        return selected

    def select(self, *, seed: int, industry: str | None = None,
               obligations: tuple[str, ...] = ()) -> dict[str, Any]:
        """Deterministic weighted selection with explicit probabilities and gaps."""
        import random
        if industry is not None and industry not in self.nodes:
            raise ValueError(f"unknown industry root: {industry}")
        rng = random.Random(seed)
        roots = [self.nodes[i] for i in ([industry] if industry else self.industries())]
        if not roots:
            raise ValueError(f"unknown industry root: {industry}")
        total = sum(node.generator_weight for node in roots)
        pick = rng.uniform(0, total)
        acc = 0.0
        chosen = roots[-1]
        probabilities = {node.node_id: node.generator_weight / total for node in roots}
        for node in roots:
            acc += node.generator_weight
            if pick <= acc:
                chosen = node
                break
        tree_ids = self._subtree(chosen.node_id)
        available = sorted(node.node_id for node in self.nodes.values()
                           if node.kind == "obligation" and node.node_id in tree_ids)
        chosen_obligations = obligations or tuple(
            sorted({obligation for obligation in available
                    if rng.random() < .75}, key=str) or available[:1])
        selection = {"version": SCENARIO_TREE_VERSION, "seed": seed,
                     "industry": chosen.node_id, "industry_probabilities": probabilities,
                     "obligations": list(chosen_obligations)}
        selection.update(self.resolve(selection))
        return selection

    def resolve(self, selection: Mapping[str, Any]) -> dict[str, Any]:
        """Expand a selection into a typed WorkflowPackage with static constraints."""
        industry = selection.get("industry")
        if industry not in self.nodes or self.nodes[industry].kind != "industry":
            raise ValueError(f"selection root is not an industry: {industry!r}")
        obligations = list(selection.get("obligations") or [])
        tree_ids = self._subtree(industry)
        for obligation in obligations:
            if obligation not in tree_ids or self.nodes[obligation].kind != "obligation":
                raise ValueError(f"obligation {obligation!r} is outside industry {industry}")
        obligations = self._propagate_prerequisites(industry, obligations)
        selected_obligations = set(obligations)
        industry_tree = self._subtree(industry)
        active: set[str] = {industry, *obligations}
        # A workflow/asset/tool/evidence node joins only when it lies inside the
        # selected industry and every obligation it descends from (over all parent
        # paths) is selected; multi-parent stages must not leak a sibling or foreign
        # obligation's subtree into the package.
        obligation_scope = {node_id for node_id in industry_tree
                            if self._obligation_ancestors(node_id) <= selected_obligations}
        active |= obligation_scope
        # Industry-level roles and their permission provides are shared infrastructure.
        for node in self.nodes.values():
            if node.kind == "role" and industry in node.parent_ids:
                active.add(node.node_id)
        provides = self._provides(active)
        package = {"version": SCENARIO_TREE_VERSION, "industry": industry,
                   "obligations": obligations,
                   "roles": [n.node_id for n in self._by_kind(active, "role")],
                   "assets": [n.node_id for n in self._by_kind(active, "asset")],
                   "tools": [n.node_id for n in self._by_kind(active, "tool")],
                   "evidence_sources": [n.node_id for n in self._by_kind(active, "evidence_source")],
                   "stages": [n.node_id for n in self._by_kind(active, "workflow_stage")],
                   "events": sorted({edge.get("event") for node in self._by_kind(active, "tool")
                                     for edge in node.effect_bindings}),
                   "coverage_cells": sorted({self.nodes[i].coverage_cell for i in active}),
                   "selected_node_sha256": canonical_sha256(sorted(active))}
        self.check_static(package, active, provides)
        return package

    def _provides(self, active: set[str]) -> set[str]:
        provides: set[str] = set()
        for node_id in active:
            provides.update(self.nodes[node_id].provides)
        return provides

    def _by_kind(self, active: set[str], kind: str) -> list[BranchNode]:
        return sorted((self.nodes[i] for i in active if self.nodes[i].kind == kind),
                      key=lambda node: node.node_id)

    def check_static(self, package: Mapping[str, Any], active: set[str] | None = None,
                     provides: set[str] | None = None) -> list[str]:
        """Fail closed on cross-domain tooling, unsatisfied requires and unknown ids."""
        active = active or set(package.get("stages", [])) | {package["industry"]}
        provides = provides or self._provides(active)
        violations: list[str] = []
        industry = package["industry"]
        allowed_root = self.nodes[industry].provides[0] if self.nodes[industry].provides else None
        for node_id in sorted(active):
            node = self.nodes.get(node_id)
            if node is None:
                violations.append(f"UNKNOWN_NODE:{node_id}")
                continue
            for required in node.requires:
                if required not in provides:
                    violations.append(f"UNSATISFIED_REQUIREMENT:{node_id}:{required}")
            for parent in node.parent_ids:
                if parent in self.nodes and self.nodes[parent].kind == "industry" \
                        and parent != industry:
                    violations.append(f"CROSS_INDUSTRY_EDGE:{node_id}:{parent}")
            if node.kind == "tool":
                for parent in node.parent_ids:
                    target = self.nodes.get(parent)
                    if target is not None and target.kind in {"role", "asset"} \
                            and self._root_of(parent) != allowed_root:
                        violations.append(f"CROSS_DOMAIN_TOOL:{node_id}:{parent}")
        if violations:
            raise ValueError("TREE_CONSTRAINT_INVALID: " + "; ".join(violations))
        return []

    def _root_of(self, node_id: str) -> str | None:
        node = self.nodes.get(node_id)
        while node is not None and node.kind != "industry":
            node = self.nodes.get(node.parent_ids[0]) if node.parent_ids else None
        return node.provides[0] if node and node.provides else None

    def coverage_gaps(self, produced_cells: set[str]) -> dict[str, Any]:
        """Explain which coverage cells remain unproduced after a planning batch."""
        all_cells = {node.coverage_cell for node in self.nodes.values()}
        missing = sorted(all_cells - produced_cells)
        return {"total_cells": len(all_cells), "produced_cells": len(produced_cells),
                "missing_cells": missing,
                "note": "cells are planning guidance, not structural novelty claims"}

    def bind_mechanism_slots(self, package: Mapping[str, Any]) -> dict[str, Any]:
        """Declare where suite mechanism interventions may attach in this package."""
        industry = package["industry"]
        return {"industry": industry,
                "propagation_events": package["events"],
                "verification_stages": [stage for stage in package["stages"]
                                        if "verify" in stage],
                "tools_by_role": {role: [tool for tool in package["tools"]
                                         if role in self.nodes[tool].parent_ids]
                                  for role in package["roles"]},
                "assets_by_stage": {stage: [node.node_id for node in self.nodes.values()
                                            if node.kind == "asset" and stage in node.parent_ids]
                                    for stage in package["stages"]}}


def tree_spec() -> dict[str, Any]:
    return ScenarioBranchTree().spec()
