"""Accountability reconstruction with an optional executable business workflow."""
from copy import deepcopy
from dataclasses import replace

from .bounded_compiler import BoundedWorldCompiler
from .business_binding import BusinessBinding, binding_world_view


class T323DynaCompiler(BoundedWorldCompiler):
    adapter_version = "ioabench.v5.t323-accountability-compiler/1.1.1"

    def __init__(self):
        super().__init__("T323-DYNA")

    def generator_constraints(self, *, subtype, difficulty):
        result = super().generator_constraints(subtype=subtype, difficulty=difficulty)
        result["schema"]["properties"]["suite_payload"]["properties"]["business_binding"] = {"type": "object"}
        result["schema"]["properties"]["suite_payload"]["properties"]["business_transaction"] = {
            "const": "workflow_transaction_v1"}
        result["program_fixed_semantics"]["business_transaction"] = (
            "When enabled, the program binds the work-order domain and subject prefix to the business plan; "
            "the validated neutral narrative suffix remains in the work order and its source documents.")
        return result

    def fidelity_report(self, blueprint):
        result = super().fidelity_report(blueprint)
        payload = blueprint.get("suite_payload", {}) if isinstance(blueprint, dict) else {}
        if "business_binding" in payload:
            errors = BusinessBinding.from_dict(payload["business_binding"]).validate_integrity()
            result["gaps"].extend({"code": "CAPABILITY_GAP", "field_path": "/suite_payload/business_binding",
                                   "reason": reason} for reason in errors)
            result["faithful"] = not result["gaps"]
            result["proposal_to_runtime_mapping"].append({
                "blueprint_path": "/suite_payload/business_binding", "runtime_path": "/world/business_binding",
                "consumer": "T323DynamicScenario business duties, tools and receipt-chain events"})
        if "business_transaction" in payload:
            if not payload.get("business_binding", {}).get("plan"):
                result["gaps"].append({"code": "CAPABILITY_GAP", "field_path": "/suite_payload/business_transaction",
                    "reason": "transaction context requires a compiled business plan"})
            result["proposal_to_runtime_mapping"].append({
                "blueprint_path": "/suite_payload/business_transaction", "runtime_path": "/world/business_transaction",
                "consumer": "shared work order, source document, business receipts and progress"})
            result["proposal_to_runtime_mapping"].append({
                "blueprint_path": "/world_edits", "runtime_path": "/world/work_order/subject",
                "consumer": "neutral narrative suffix after program-bound business objects"})
            result["faithful"] = not result["gaps"]
        for mapping in result["proposal_to_runtime_mapping"]:
            mapping["status"] = "MAPPED"
        return result

    def compile_pair(self, blueprint, *, seed):
        if "business_binding" not in blueprint["suite_payload"]:
            return BoundedWorldCompiler(self.suite_id).compile_pair(blueprint, seed=seed)
        report = self.fidelity_report(blueprint)
        if report["gaps"]:
            raise ValueError(f"invalid accountability blueprint: {report['gaps']}")
        pair = super().compile_pair(blueprint, seed=seed)
        result = tuple(replace(case, world={**deepcopy(case.world),
            "business_binding": binding_world_view(blueprint["suite_payload"]["business_binding"])},
            provenance={**case.provenance, "proposal_to_runtime_mapping": deepcopy(report["proposal_to_runtime_mapping"])})
            for case in pair)
        if "business_transaction" in blueprint["suite_payload"]:
            from ioabench.v5.dynamic.t323_transaction import bind_world
            result = tuple(replace(case, world=world, domain=domain) for case in result
                           for world, domain in (bind_world(case.world, seed=seed),))
        return result

    def verify_arm_delta(self, control, risk):
        findings = super().verify_arm_delta(control, risk)
        if control.world.get("business_binding") != risk.world.get("business_binding"):
            findings.append("business binding differs between arms (single intervention violated)")
        if control.world.get("business_transaction") != risk.world.get("business_transaction"):
            findings.append("business transaction differs between arms")
        return findings
