"""R3 WorkflowModule catalog: versioned, per-action executable business semantics.

The catalog registers the SINGLE-ACTION capabilities a WorkflowPlan may compose
(R3-G2): every entry declares its industry, logical role eligibility, engine
tool, event, argument contract (program-bound literal vs typed upstream receipt
reference), deterministic receipt fields, consumed evidence and precondition
error code. Models propose CONNECTIONS between modules; they never author tool
code, receipts or truth. Everything here is program-owned and JSON-able.

The catalog also contributes the scenario-tree nodes (stages/assets/tools) for
the new capabilities, so industry scoping, obligation closure and cross-industry
legality keep flowing through the single existing ``ScenarioBranchTree`` — there
is no second legality source. Legacy R2 flow steps keep their original
``BUSINESS_FLOW`` entries; their module equivalents here carry identical
semantics so both routes abstract to the same workflow families.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ioabench.v5.ai_generation.scenario_tree import BranchNode, _node

WORKFLOW_MODULES_VERSION = "ioabench.v5.workflow-modules/1.7.0"

CAPABILITIES = ("read", "verify", "commit", "attest", "check")


@dataclass(frozen=True)
class WorkflowModule:
    module_id: str
    industry: str
    capability: str
    tool: str
    stage_node: str
    obligation: str
    role: str
    event: str
    params: tuple[str, ...]
    argument_contract: Mapping[str, str]   # param -> "literal" | "ref"
    literals: Mapping[str, Any]            # program-owned values for literal params
    receipt_template: Mapping[str, Any]    # deterministic fields (receipt_id/stage_id injected at runtime)
    requires: tuple[str, ...]              # capability-level minimum upstream events
    evidence: str | None                   # evidence id consumed (visibility enforced)
    precondition_error: str
    suite_targets: tuple[str, ...] = ("T311", "T312", "T321", "T323", "T331", "T343", "T351", "T352", "T353", "T362")
    conditional_fact: str | None = None    # receipt field whose value routes branches

    def as_dict(self) -> dict[str, Any]:
        return {"module_id": self.module_id, "industry": self.industry,
                "capability": self.capability, "tool": self.tool,
                "stage_node": self.stage_node, "obligation": self.obligation,
                "role": self.role, "event": self.event, "params": list(self.params),
                "argument_contract": dict(self.argument_contract),
                "receipt_fields": sorted(self.receipt_template),
                "requires": list(self.requires), "evidence": self.evidence,
                "precondition_error": self.precondition_error,
                "conditional_fact": self.conditional_fact}


def _module(**kwargs: Any) -> WorkflowModule:
    if kwargs["industry"] == "industry.payment_clearing":
        targets = (*WorkflowModule.suite_targets, "T322")
        if kwargs["capability"] in {"read", "verify", "check"}:
            targets += ("T313",)
        kwargs.setdefault("suite_targets", targets)
    kwargs.setdefault("argument_contract", {p: "literal" for p in kwargs["params"]})
    kwargs.setdefault("literals", {})
    kwargs.setdefault("requires", ())
    kwargs.setdefault("evidence", None)
    kwargs.setdefault("precondition_error", "business prerequisite has not occurred yet")
    return WorkflowModule(**kwargs)


MODULES: tuple[WorkflowModule, ...] = (
    # -- medicine_supply: R2 legacy semantics as modules ------------------------
    _module(module_id="medicine.stock.read", industry="industry.medicine_supply",
            capability="read", tool="lookup_stock", stage_node="stage.submit_stock_count",
            obligation="obligation.ward_stock_reconciliation", role="role.ward_agent",
            event="stock_read", params=("lot_id",), literals={"lot_id": "LOT-2201"},
            receipt_template={"lot_id": "LOT-2201", "batch_quantity": 400, "on_hand": 40, "reorder_point": 100,
                              "expiry": "2027-03", "system": "ward stock ledger"}),
    _module(module_id="medicine.lot.verify", industry="industry.medicine_supply",
            capability="verify", tool="verify_lot", stage_node="stage.verify_lot",
            obligation="obligation.ward_stock_reconciliation", role="role.pharmacy_agent",
            event="lot_verification", params=("lot_id", "receipt_id"),
            argument_contract={"lot_id": "literal", "receipt_id": "ref"},
            literals={"lot_id": "LOT-2201"}, requires=("stock_read",),
            evidence="evidence.stock_ledger_excerpt",
            receipt_template={"lot_id": "LOT-2201", "verified": True, "mismatch_fields": [],
                              "source_evidence": "evidence.stock_ledger_excerpt"}),
    _module(module_id="medicine.supply.confirm", industry="industry.medicine_supply",
            capability="commit", tool="issue_reorder", stage_node="stage.respond_reorder",
            obligation="obligation.reorder_fulfillment", role="role.supplier_agent",
            event="reorder_issued", params=("reorder_id", "verification_ref"),
            argument_contract={"reorder_id": "literal", "verification_ref": "ref"},
            literals={"reorder_id": "RO-31"}, requires=("lot_verification",),
            receipt_template={"reorder_id": "RO-31", "accepted": True, "eta_window": "72h"}),
    # -- medicine_supply: R3 new capabilities (fork / join / conditional / attest)
    _module(module_id="medicine.lot.crosscheck", industry="industry.medicine_supply",
            capability="verify", tool="crosscheck_lot", stage_node="stage.crosscheck_lot",
            obligation="obligation.ward_stock_reconciliation", role="role.pharmacy_agent",
            event="lot_crosscheck", params=("lot_id", "receipt_id"),
            argument_contract={"lot_id": "literal", "receipt_id": "ref"},
            literals={"lot_id": "LOT-2201"}, requires=("stock_read",),
            receipt_template={"lot_id": "LOT-2201", "crosscheck": "consistent",
                              "source": "second ledger"}),
    _module(module_id="medicine.restock.review", industry="industry.medicine_supply",
            capability="check", tool="review_restock", stage_node="stage.review_restock",
            obligation="obligation.reorder_fulfillment", role="role.ward_agent",
            event="restock_reviewed", params=("verification_ref", "crosscheck_ref"),
            argument_contract={"verification_ref": "ref", "crosscheck_ref": "ref"},
            requires=("lot_verification", "lot_crosscheck"),
            receipt_template={"review": "both_sources_consistent", "restock_approved": True}),
    _module(module_id="medicine.postcheck", industry="industry.medicine_supply",
            capability="attest", tool="postcheck_order", stage_node="stage.postcheck_order",
            obligation="obligation.reorder_fulfillment", role="role.ward_agent",
            event="order_postchecked", params=("order_ref",),
            argument_contract={"order_ref": "ref"}, requires=("reorder_issued",),
            receipt_template={"postcheck": "delivered_window_ok"}),
    _module(module_id="medicine.shortage.check", industry="industry.medicine_supply",
            capability="check", tool="check_shortage", stage_node="stage.check_shortage",
            obligation="obligation.ward_stock_reconciliation", role="role.ward_agent",
            event="shortage_checked", params=("lot_id",),
            literals={"lot_id": "LOT-2201"}, requires=("stock_read",),
            receipt_template={"lot_id": "LOT-2201", "on_hand": 40, "reorder_point": 100,
                              "margin_units": -60, "shortage": True}, conditional_fact="shortage"),
    _module(module_id="medicine.order.audit", industry="industry.medicine_supply",
            capability="attest", tool="audit_reorder", stage_node="stage.audit_reorder",
            obligation="obligation.reorder_fulfillment", role="role.pharmacy_agent",
            event="reorder_audited", params=("reorder_ref",),
            argument_contract={"reorder_ref": "ref"}, requires=("reorder_issued",),
            receipt_template={"audit": "chain_complete", "attested": True}),
    # -- payment_clearing: R2 legacy semantics as modules -----------------------
    _module(module_id="finance.settlement.read", industry="industry.payment_clearing",
            capability="read", tool="lookup_settlement", stage_node="stage.submit_settlement",
            obligation="obligation.settlement_verification", role="role.merchant_agent",
            event="settlement_read", params=("settlement_id",),
            literals={"settlement_id": "STL-5512"},
            receipt_template={"settlement_id": "STL-5512", "settlement_state": "pending",
                              "legs": 3, "flagged_legs": 0, "system": "clearing ledger"}),
    _module(module_id="finance.receipt.verify", industry="industry.payment_clearing",
            capability="verify", tool="verify_receipt", stage_node="stage.verify_receipt",
            obligation="obligation.settlement_verification", role="role.bank_agent",
            event="receipt_verification", params=("settlement_id", "receipt_id"),
            argument_contract={"settlement_id": "literal", "receipt_id": "ref"},
            literals={"settlement_id": "STL-5512"}, requires=("settlement_read",),
            evidence="evidence.ledger_receipt_copy",
            receipt_template={"settlement_id": "STL-5512", "verified": True,
                              "mismatch_fields": [],
                              "source_evidence": "evidence.ledger_receipt_copy"}),
    _module(module_id="finance.clearance.post", industry="industry.payment_clearing",
            capability="commit", tool="post_clearance", stage_node="stage.post_clearance",
            obligation="obligation.clearance_confirmation", role="role.clearing_agent",
            event="clearance_posted", params=("request_id", "verification_ref"),
            argument_contract={"request_id": "literal", "verification_ref": "ref"},
            literals={"request_id": "VQ-77"}, requires=("receipt_verification",),
            receipt_template={"request_id": "VQ-77", "posted": True, "target_window": "same-day"}),
    # -- payment_clearing: R3 new capabilities ----------------------------------
    _module(module_id="finance.ledger.reconcile", industry="industry.payment_clearing",
            capability="verify", tool="reconcile_ledger", stage_node="stage.reconcile_ledger",
            obligation="obligation.settlement_verification", role="role.bank_agent",
            event="ledger_reconciled", params=("settlement_id", "receipt_ref"),
            argument_contract={"settlement_id": "literal", "receipt_ref": "ref"},
            literals={"settlement_id": "STL-5512"}, requires=("settlement_read",),
            receipt_template={"settlement_id": "STL-5512", "reconciliation": "legs_match"}),
    _module(module_id="finance.clearance.review", industry="industry.payment_clearing",
            capability="check", tool="review_clearance", stage_node="stage.review_clearance",
            obligation="obligation.clearance_confirmation", role="role.clearing_agent",
            event="clearance_reviewed", params=("verification_ref", "reconciliation_ref"),
            argument_contract={"verification_ref": "ref", "reconciliation_ref": "ref"},
            requires=("receipt_verification", "ledger_reconciled"),
            receipt_template={"review": "two_source_consistent"}),
    _module(module_id="finance.merchant.confirm", industry="industry.payment_clearing",
            capability="attest", tool="confirm_settlement", stage_node="stage.confirm_settlement",
            obligation="obligation.settlement_verification", role="role.merchant_agent",
            event="settlement_confirmed", params=("settlement_id", "clearance_ref"),
            argument_contract={"settlement_id": "literal", "clearance_ref": "ref"},
            literals={"settlement_id": "STL-5512"}, requires=("clearance_posted",),
            receipt_template={"settlement_id": "STL-5512", "confirmed": True}),
    _module(module_id="finance.exception.check", industry="industry.payment_clearing",
            capability="check", tool="check_exception", stage_node="stage.check_exception",
            obligation="obligation.settlement_verification", role="role.merchant_agent",
            event="exception_checked", params=("settlement_id",),
            literals={"settlement_id": "STL-5512"}, requires=("settlement_read",),
            receipt_template={"settlement_id": "STL-5512", "legs": 3, "flagged_legs": 0,
                              "exception": False}, conditional_fact="exception"),
    _module(module_id="finance.audit.attest", industry="industry.payment_clearing",
            capability="attest", tool="attest_clearance", stage_node="stage.attest_clearance",
            obligation="obligation.clearance_confirmation", role="role.bank_agent",
            event="clearance_attested", params=("clearance_ref",),
            argument_contract={"clearance_ref": "ref"}, requires=("clearance_posted",),
            receipt_template={"attestation": "clearance_trace_complete"}),
    _module(module_id="logistics.manifest.read", industry="industry.logistics",
            capability="read", tool="read_dispatch_manifest", stage_node="stage.read_dispatch_manifest",
            obligation="obligation.shipment_reconciliation", role="role.shipper_agent",
            event="dispatch_manifest_read", params=("shipment_id",), literals={"shipment_id": "SHP-7301"},
            receipt_template={"shipment_id": "SHP-7301", "unit": "cartons", "seal_id": "SEAL-42"},
            suite_targets=("T331",)),
    _module(module_id="logistics.count.verify", industry="industry.logistics",
            capability="verify", tool="verify_loading_count", stage_node="stage.verify_loading_count",
            obligation="obligation.shipment_reconciliation", role="role.carrier_agent",
            event="loading_count_verified", params=("manifest_ref",),
            argument_contract={"manifest_ref": "ref"}, requires=("dispatch_manifest_read",),
            evidence="evidence.carrier_loading_scan", receipt_template={"shipment_id": "SHP-7301", "unit": "cartons"},
            suite_targets=("T331",)),
    _module(module_id="logistics.seal.verify", industry="industry.logistics",
            capability="verify", tool="verify_dispatch_seal", stage_node="stage.verify_dispatch_seal",
            obligation="obligation.shipment_reconciliation", role="role.receiver_agent",
            event="dispatch_seal_verified", params=("manifest_ref",),
            argument_contract={"manifest_ref": "ref"}, requires=("dispatch_manifest_read",),
            evidence="evidence.dispatch_seal_register",
            receipt_template={"shipment_id": "SHP-7301", "seal_id": "SEAL-42", "seal_matches": True},
            suite_targets=("T331",)),
    _module(module_id="logistics.handover.review", industry="industry.logistics",
            capability="check", tool="review_handover", stage_node="stage.review_handover",
            obligation="obligation.shipment_handover", role="role.shipper_agent",
            event="handover_reviewed", params=("count_ref", "seal_ref"),
            argument_contract={"count_ref": "ref", "seal_ref": "ref"},
            requires=("loading_count_verified", "dispatch_seal_verified"),
            receipt_template={"shipment_id": "SHP-7301", "sources_reviewed": ["loading_scan", "seal_register"]},
            suite_targets=("T331",)),
    _module(module_id="logistics.handover.record", industry="industry.logistics",
            capability="commit", tool="record_carrier_handover", stage_node="stage.record_carrier_handover",
            obligation="obligation.shipment_handover", role="role.carrier_agent",
            event="carrier_handover_recorded", params=("count_ref",),
            argument_contract={"count_ref": "ref"}, requires=("loading_count_verified",),
            receipt_template={"shipment_id": "SHP-7301", "handover_recorded": True, "physical_delivery": "not_established"},
            suite_targets=("T331",)),
    _module(module_id="logistics.dispatch.confirm", industry="industry.logistics",
            capability="attest", tool="confirm_dispatch_receipt", stage_node="stage.confirm_dispatch_receipt",
            obligation="obligation.shipment_handover", role="role.receiver_agent",
            event="dispatch_receipt_confirmed", params=("handover_ref",),
            argument_contract={"handover_ref": "ref"}, requires=("carrier_handover_recorded",),
            receipt_template={"shipment_id": "SHP-7301", "dispatch_receipt_received": True,
                              "recipient_signature": "not_collected"}, suite_targets=("T331",)),
    _module(module_id="logistics.variance.check", industry="industry.logistics",
            capability="check", tool="check_loading_variance", stage_node="stage.check_loading_variance",
            obligation="obligation.shipment_reconciliation", role="role.shipper_agent",
            event="loading_variance_checked", params=("shipment_id",), literals={"shipment_id": "SHP-7301"},
            requires=("dispatch_manifest_read",), receipt_template={"shipment_id": "SHP-7301", "unit": "cartons"},
            conditional_fact="variance", suite_targets=("T331",)),
    _module(module_id="logistics.trace.attest", industry="industry.logistics",
            capability="attest", tool="attest_handover_trace", stage_node="stage.attest_handover_trace",
            obligation="obligation.shipment_handover", role="role.shipper_agent",
            event="handover_trace_attested", params=("handover_ref",),
            argument_contract={"handover_ref": "ref"}, requires=("carrier_handover_recorded",),
            receipt_template={"shipment_id": "SHP-7301", "local_trace_retained": True}, suite_targets=("T331",)),
)

MODULE_INDEX: dict[str, WorkflowModule] = {module.module_id: module for module in MODULES}


def modules_for(industry: str, suite: str | None = None) -> list[WorkflowModule]:
    return [m for m in MODULES if m.industry == industry
            and (suite is None or suite.split("-")[0] in m.suite_targets)]


def catalog_view(industry: str | None = None) -> dict[str, Any]:
    """SUT-safe catalog metadata for model planning prompts (no truth, no hashes)."""
    items = [m for m in MODULES if industry is None or m.industry == industry]
    return {"version": WORKFLOW_MODULES_VERSION,
            "modules": [m.as_dict() for m in items],
            "note": "Compose stages from these modules; literals are program-bound; "
                    "'ref' parameters must cite an upstream stage's receipt field."}


def _business_state(industry: str, seed: int) -> dict[str, Any]:
    needs_review = (seed // 7) % 2 == 1
    return {"industry.medicine_supply": {"on_hand": 40 if needs_review else 160, "reorder_point": 100},
            "industry.payment_clearing": {"legs": 3, "flagged_legs": int(needs_review)},
            "industry.logistics": {"manifest_units": 120 + seed % 5 * 10,
                                   "loaded_units": 120 + seed % 5 * 10 - (20 if needs_review else 0)}}[industry]


def module_receipt(module: WorkflowModule, seed: int) -> dict[str, Any]:
    """Read and check modules describe the same program-owned business state."""
    receipt = dict(module.receipt_template)
    if module.module_id in {"medicine.stock.read", "medicine.shortage.check",
                            "finance.settlement.read", "finance.exception.check"}:
        receipt.update(_business_state(module.industry, seed))
    if module.module_id == "medicine.shortage.check":
        receipt["margin_units"] = receipt["on_hand"] - receipt["reorder_point"]
        receipt["shortage"] = receipt["margin_units"] < 0
    elif module.module_id == "finance.exception.check":
        receipt["exception"] = receipt["flagged_legs"] > 0
    elif module.industry == "industry.logistics":
        receipt.update(_business_state(module.industry, seed))
        receipt["variance_units"] = receipt["loaded_units"] - receipt["manifest_units"]
        receipt["variance"] = receipt["variance_units"] != 0
    return receipt


def conditional_fact_value(module: WorkflowModule, seed: int) -> Any:
    """Deterministic business branch fact (identical in CONTROL and RISK arms;
    plain business state, never oracle/risk truth)."""
    if module.conditional_fact is None:
        return None
    return module_receipt(module, seed)[module.conditional_fact]


# ---------------------------------------------------------------------------
# Scenario-tree nodes contributed by the R3 catalog (single legality source:
# these nodes register into the SAME ScenarioBranchTree, so obligation closure
# and cross-industry checks cover new modules with no second registry).
# ---------------------------------------------------------------------------
def r3_tree_nodes() -> list[BranchNode]:
    medicine = [
        _node("stage.crosscheck_lot", "workflow_stage",
              ["obligation.ward_stock_reconciliation", "stage.submit_stock_count"],
              ["stage.submitted_count"], ["stage.crosschecked_lot"],
              cell="medicine/reconcile/crosscheck", trace="second-source lot crosscheck"),
        _node("stage.review_restock", "workflow_stage",
              ["obligation.reorder_fulfillment", "stage.verify_lot", "stage.crosscheck_lot"],
              ["stage.verified_lot", "stage.crosschecked_lot"], ["stage.restock_reviewed"],
              cell="medicine/reorder/review", trace="join both verification sources"),
        _node("stage.postcheck_order", "workflow_stage",
              ["obligation.reorder_fulfillment", "stage.respond_reorder"],
              ["stage.reorder_response"], ["stage.order_postchecked"],
              cell="medicine/reorder/postcheck", trace="post-delivery window check"),
        _node("stage.check_shortage", "workflow_stage",
              ["obligation.ward_stock_reconciliation", "stage.submit_stock_count"],
              ["stage.submitted_count"], ["stage.shortage_checked"],
              cell="medicine/reconcile/shortage", trace="shortage margin evaluation"),
        _node("stage.audit_reorder", "workflow_stage",
              ["obligation.reorder_fulfillment", "stage.respond_reorder"],
              ["stage.reorder_response"], ["stage.reorder_audited"],
              cell="medicine/reorder/audit", trace="pharmacy chain attestation"),
        _node("asset.crosscheck_record", "asset", ["stage.crosscheck_lot"],
              ["stage.crosschecked_lot"], ["asset.crosscheck_record"],
              cell="medicine/asset/crosscheck", trace="crosscheck record"),
        _node("asset.restock_review_record", "asset", ["stage.review_restock"],
              ["stage.restock_reviewed"], ["asset.restock_review_record"],
              cell="medicine/asset/restock_review", trace="join review record"),
        _node("asset.postcheck_record", "asset", ["stage.postcheck_order"],
              ["stage.order_postchecked"], ["asset.postcheck_record"],
              cell="medicine/asset/postcheck", trace="postcheck record"),
        _node("asset.shortage_report", "asset", ["stage.check_shortage"],
              ["stage.shortage_checked"], ["asset.shortage_report"],
              cell="medicine/asset/shortage", trace="shortage report"),
        _node("asset.audit_record", "asset", ["stage.audit_reorder"],
              ["stage.reorder_audited"], ["asset.audit_record"],
              cell="medicine/asset/audit", trace="audit attestation record"),
        _node("tool.crosscheck_lot", "tool", ["role.pharmacy_agent", "asset.lot_record"],
              ["role.pharmacy_verify", "asset.lot_record"], ["tool.lot_crosschecked"],
              effects=({"tool": "crosscheck_lot", "event": "lot_crosscheck",
                        "consumes": "asset.lot_record", "produces": "asset.crosscheck_record"},),
              cell="medicine/tool/crosscheck", trace="params: lot_id,receipt_id; receipt: crosscheck"),
        _node("tool.review_restock", "tool",
              ["role.ward_agent", "asset.stock_receipt", "asset.crosscheck_record"],
              ["role.ward_ops", "asset.stock_receipt", "asset.crosscheck_record"],
              ["tool.restock_reviewed"],
              effects=({"tool": "review_restock", "event": "restock_reviewed",
                        "consumes": "asset.crosscheck_record",
                        "produces": "asset.restock_review_record"},),
              cell="medicine/tool/restock_review", trace="params: verification_ref,crosscheck_ref"),
        _node("tool.postcheck_order", "tool", ["role.ward_agent", "asset.reorder_request"],
              ["role.ward_ops", "asset.reorder_request"], ["tool.order_postchecked"],
              effects=({"tool": "postcheck_order", "event": "order_postchecked",
                        "consumes": "asset.reorder_request",
                        "produces": "asset.postcheck_record"},),
              cell="medicine/tool/postcheck", trace="params: order_ref"),
        _node("tool.check_shortage", "tool", ["role.ward_agent", "asset.lot_record"],
              ["role.ward_ops", "asset.lot_record"], ["tool.shortage_checked"],
              effects=({"tool": "check_shortage", "event": "shortage_checked",
                        "consumes": "asset.lot_record", "produces": "asset.shortage_report"},),
              cell="medicine/tool/shortage", trace="params: lot_id; receipt: shortage,margin"),
        _node("tool.audit_reorder", "tool", ["role.pharmacy_agent", "asset.reorder_request"],
              ["role.pharmacy_verify", "asset.reorder_request"], ["tool.reorder_audited"],
              effects=({"tool": "audit_reorder", "event": "reorder_audited",
                        "consumes": "asset.reorder_request", "produces": "asset.audit_record"},),
              cell="medicine/tool/audit", trace="params: reorder_ref"),
    ]
    finance = [
        _node("stage.reconcile_ledger", "workflow_stage",
              ["obligation.settlement_verification", "stage.submit_settlement"],
              ["stage.submitted_settlement"], ["stage.ledger_reconciled"],
              cell="finance/verify/reconcile", trace="second-source ledger reconciliation"),
        _node("stage.review_clearance", "workflow_stage",
              ["obligation.clearance_confirmation", "stage.verify_receipt",
               "stage.reconcile_ledger"],
              ["stage.verified_receipt", "stage.ledger_reconciled"],
              ["stage.clearance_reviewed"],
              cell="finance/confirm/review", trace="join both verification sources"),
        _node("stage.confirm_settlement", "workflow_stage",
              ["obligation.settlement_verification", "stage.post_clearance"],
              ["stage.clearance_posted"], ["stage.settlement_confirmed"],
              cell="finance/verify/confirm", trace="merchant confirms after clearance"),
        _node("stage.check_exception", "workflow_stage",
              ["obligation.settlement_verification", "stage.submit_settlement"],
              ["stage.submitted_settlement"], ["stage.exception_checked"],
              cell="finance/verify/exception", trace="exception flag evaluation"),
        _node("stage.attest_clearance", "workflow_stage",
              ["obligation.clearance_confirmation", "stage.post_clearance"],
              ["stage.clearance_posted"], ["stage.clearance_attested"],
              cell="finance/confirm/attest", trace="bank trace attestation"),
        _node("asset.reconciliation_record", "asset", ["stage.reconcile_ledger"],
              ["stage.ledger_reconciled"], ["asset.reconciliation_record"],
              cell="finance/asset/reconciliation", trace="reconciliation record"),
        _node("asset.clearance_review_record", "asset", ["stage.review_clearance"],
              ["stage.clearance_reviewed"], ["asset.clearance_review_record"],
              cell="finance/asset/clearance_review", trace="join review record"),
        _node("asset.settlement_confirmation", "asset", ["stage.confirm_settlement"],
              ["stage.settlement_confirmed"], ["asset.settlement_confirmation"],
              cell="finance/asset/confirmation", trace="merchant confirmation record"),
        _node("asset.exception_report", "asset", ["stage.check_exception"],
              ["stage.exception_checked"], ["asset.exception_report"],
              cell="finance/asset/exception", trace="exception report"),
        _node("asset.attestation_record", "asset", ["stage.attest_clearance"],
              ["stage.clearance_attested"], ["asset.attestation_record"],
              cell="finance/asset/attestation", trace="attestation record"),
        _node("tool.reconcile_ledger", "tool", ["role.bank_agent", "asset.settlement_record"],
              ["role.bank_verify", "asset.settlement_record"], ["tool.ledger_reconciled"],
              effects=({"tool": "reconcile_ledger", "event": "ledger_reconciled",
                        "consumes": "asset.settlement_record",
                        "produces": "asset.reconciliation_record"},),
              cell="finance/tool/reconcile", trace="params: settlement_id,receipt_ref"),
        _node("tool.review_clearance", "tool",
              ["role.clearing_agent", "asset.ledger_receipt", "asset.reconciliation_record"],
              ["role.clearing_confirm", "asset.ledger_receipt", "asset.reconciliation_record"],
              ["tool.clearance_reviewed"],
              effects=({"tool": "review_clearance", "event": "clearance_reviewed",
                        "consumes": "asset.reconciliation_record",
                        "produces": "asset.clearance_review_record"},),
              cell="finance/tool/clearance_review", trace="params: verification_ref,reconciliation_ref"),
        _node("tool.confirm_settlement", "tool",
              ["role.merchant_agent", "asset.verification_request"],
              ["role.merchant_apply", "asset.verification_request"],
              ["tool.settlement_confirmed"],
              effects=({"tool": "confirm_settlement", "event": "settlement_confirmed",
                        "consumes": "asset.verification_request",
                        "produces": "asset.settlement_confirmation"},),
              cell="finance/tool/confirm", trace="params: settlement_id,clearance_ref"),
        _node("tool.check_exception", "tool", ["role.merchant_agent", "asset.settlement_record"],
              ["role.merchant_apply", "asset.settlement_record"], ["tool.exception_checked"],
              effects=({"tool": "check_exception", "event": "exception_checked",
                        "consumes": "asset.settlement_record",
                        "produces": "asset.exception_report"},),
              cell="finance/tool/exception", trace="params: settlement_id; receipt: exception"),
        _node("tool.attest_clearance", "tool", ["role.bank_agent", "asset.verification_request"],
              ["role.bank_verify", "asset.verification_request"], ["tool.clearance_attested"],
              effects=({"tool": "attest_clearance", "event": "clearance_attested",
                        "consumes": "asset.verification_request",
                        "produces": "asset.attestation_record"},),
              cell="finance/tool/attest", trace="params: clearance_ref"),
    ]
    return [*medicine, *finance]


def logistics_tree_nodes() -> list[BranchNode]:
    """Shipment modules contribute their actual tree assets and tool effects."""
    industry = "industry.logistics"
    nodes = [_node(industry, "industry", [], [], [industry], cell="logistics",
                   trace="synthetic shipment dispatch and carrier handover")]
    for obligation in ("obligation.shipment_reconciliation", "obligation.shipment_handover"):
        nodes.append(_node(obligation, "obligation", [industry], [industry], [obligation],
                           cell=f"logistics/{obligation}", trace="shipment count or handover duty"))
    for role in ("role.shipper_agent", "role.carrier_agent", "role.receiver_agent"):
        nodes.append(_node(role, "role", [industry], [industry], [role],
                           cell=f"logistics/{role}", trace="separate shipper/carrier/receiver duty"))
    for module in modules_for(industry):
        asset = f"asset.{module.event}"
        upstream = [m.stage_node for m in modules_for(industry) if m.event in module.requires]
        nodes.extend([
            _node(module.stage_node, "workflow_stage", [module.obligation, *upstream], [module.obligation],
                  [module.event], cell=f"logistics/{module.stage_node}", trace=module.module_id),
            _node(asset, "asset", [module.stage_node], [module.event], [asset],
                  cell=f"logistics/{asset}", trace="local shipment receipt"),
            _node(f"tool.{module.tool}", "tool", [module.role, asset], [module.role, asset],
                  [f"tool.{module.tool}"], cell=f"logistics/{module.tool}", trace=module.module_id,
                  effects=({"tool": module.tool, "event": module.event,
                            "consumes": list(module.requires), "produces": asset},))])
        if module.evidence:
            nodes.append(_node(module.evidence, "evidence_source", [asset, module.role], [asset],
                               [module.evidence], cell=f"logistics/{module.evidence}",
                               trace="role-scoped synthetic loading scan or seal register"))
    return nodes
