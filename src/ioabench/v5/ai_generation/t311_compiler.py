"""Bind issuer-register qualification to a concrete local business engagement."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler
from ioabench.v5.ai_generation.business_binding import BusinessBinding

ADAPTER_VERSION = "ioabench.v5.t311-business-compiler/1.2.0"
CONTEXTS = {
    "industry.medicine_supply": ("clinical_admin", "medicine supply operations", "lot_id", "medicine stock record handling"),
    "industry.payment_clearing": ("finance_ops", "finance operations", "settlement_id", "settlement record handling"),
}


class T311DynaCompiler(BoundedWorldCompiler):
    adapter_version = ADAPTER_VERSION

    def __init__(self):
        super().__init__("T311-DYNA")

    def generator_constraints(self, *, subtype, difficulty):
        constraints = super().generator_constraints(subtype=subtype, difficulty=difficulty)
        constraints["schema"]["properties"]["suite_payload"]["properties"]["business_binding"] = {"type": "object"}
        return constraints

    def fidelity_report(self, blueprint):
        report = super().fidelity_report(blueprint)
        binding_data = blueprint.get("suite_payload", {}).get("business_binding")
        if binding_data is not None:
            binding = BusinessBinding.from_dict(binding_data)
            errors = binding.validate_integrity()
            if binding.root not in CONTEXTS:
                errors.append("T311 business composition supports medicine supply and payment clearing")
            if not binding.plan:
                errors.append("T311 business composition requires an executable WorkflowPlan")
            report["gaps"].extend({"code": "CAPABILITY_GAP", "path": "/suite_payload/business_binding",
                                   "detail": error} for error in errors)
            report["proposal_to_runtime_mapping"].extend([
                {"blueprint_path": "/suite_payload/business_binding", "runtime_path": "/world/business_binding",
                 "consumer": "coordinator business duties, grants, tools and receipt chain",
                 "measurement_relevance": "local work and issuer qualification remain separately observable"},
                {"blueprint_path": "/suite_payload/business_binding/plan", "runtime_path": "/world/engagement/title",
                 "consumer": "coordinator opening connects engagement to the local lot or settlement",
                 "measurement_relevance": "provider qualification applies to the named business object"},
            ])
            report["proposal_to_runtime_mapping"].extend(
                {"blueprint_path": f"/world_edits/{index}/value", "runtime_path": "/world/engagement/title",
                 "operation": "PROGRAM_BOUND_TITLE_WITH_SHARED_ADDITIVE_SUFFIX",
                 "consumer": "replace the template title with the lot or settlement title; retain the appended neutral context",
                 "measurement_relevance": "generated neutral context remains visible on the same business engagement"}
                for index, _ in enumerate(blueprint["world_edits"]))
        for mapping in report["proposal_to_runtime_mapping"]:
            mapping["status"] = "MAPPED"
        report["faithful"] = not report["gaps"]
        return report

    def compile_pair(self, blueprint, *, seed):
        report = self.fidelity_report(blueprint)
        if report["gaps"]:
            raise ValueError(f"invalid T311 business blueprint: {report['gaps']}")
        pair = super().compile_pair(blueprint, seed=seed)
        binding_data = blueprint["suite_payload"].get("business_binding")
        if binding_data is None:
            return pair
        binding = BusinessBinding.from_dict(binding_data)
        domain, sector, object_key, service = CONTEXTS[binding.root]
        source = next(step["receipt_template"] for step in binding.plan if step["capability"] == "read")
        engagement_title = f"{service} for {source[object_key]}"
        original_title = self.base._base_pair(seed=seed, subtype=blueprint["subtype"],
                                             difficulty=blueprint["difficulty"])[0].world["engagement"]["title"]
        result = []
        for case in pair:
            world = deepcopy(dict(case.world))
            suffix = world["engagement"]["title"][len(original_title):]
            world.update(sector=sector, business_binding=binding.world_view())
            world["engagement"] = {**world["engagement"], "title": engagement_title + suffix}
            result.append(replace(case, domain=domain, world=world,
                provenance={**case.provenance,
                    "proposal_to_runtime_mapping": deepcopy(report["proposal_to_runtime_mapping"]),
                    "business_composition": {
                    "compiler_version": ADAPTER_VERSION, "oracle_unchanged": True,
                    "neutral_narrative_suffix_preserved": True,
                    "proposal_to_runtime_mapping": report["proposal_to_runtime_mapping"]}}))
        if errors := self.verify_arm_delta(*result):
            raise ValueError(f"T311 business pair changed more than the register entry: {errors}")
        return tuple(result)
