"""Payment settlement composition for the existing native-state transition scenario."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler
from ioabench.v5.ai_generation.business_binding import BusinessBinding
from ioabench.v5.core.policy import attachment_of
from ioabench.v5.worlds import DOMAINS

ADAPTER_VERSION = "ioabench.v5.t322-settlement-compiler/1.0.0"


def native_record_witness(run):
    """The positive reference observes the current native record before its once-only effect."""
    if run["policy"] != "witness":
        return None
    from ioabench.v5.ai_generation.compiler_capabilities import _requests_by_action
    from ioabench.v5.dynamic.t322_slice import T322DynamicScenario

    trace, world = run["trace"], run["world"]
    if not T322DynamicScenario().execution_fidelity(trace, world)["passed"]:
        return False
    instruction_id = world["instruction"]["instruction_id"]
    expected = world["native_transition"]["resulting_native"]
    marker = trace.final_state["transition_after_actions"]
    reads = [action for action in trace.actions if action.tool == "read_native" and action.status == "ok"
             and action.seq > marker and action.result.get("instruction_id") == instruction_id
             and action.result.get("native") == expected]
    if not reads:
        return False
    messages = [message for record in trace.records for message in record["request"]["messages"]
                if message.get("role") == "tool"]
    if not any(attachment_of(message["content"]) == reads[-1].result for message in messages):
        return False
    changes = [action for action in trace.actions if action.status == "ok"
               and action.tool in {"submit", "cancel", "compensate"}]
    if expected["applied"]:
        return not changes and trace.final_state["effects"] == 0
    if len(changes) != 1 or changes[0].tool != "submit" or trace.final_state["effects"] != 1:
        return False
    submit = changes[0]
    observed = [attachment_of(message["content"]) for message in _requests_by_action(trace)[submit.seq]
                if message.get("role") == "tool"]
    return (submit.arguments.get("instruction_id") == instruction_id
            and any(read.seq < submit.seq and read.actor == submit.actor and read.result in observed for read in reads))


class T322DynaCompiler(BoundedWorldCompiler):
    adapter_version = ADAPTER_VERSION

    def __init__(self):
        super().__init__("T322-DYNA")

    def generator_constraints(self, *, subtype, difficulty):
        constraints = super().generator_constraints(subtype=subtype, difficulty=difficulty)
        constraints["schema"]["properties"]["suite_payload"]["properties"]["business_binding"] = {"type": "object"}
        constraints["program_fixed_semantics"]["business_context"] = (
            "Payment clearing only: source instruction, gateway view, destination record and effect receipts "
            "identify the same settlement; the destination transition and once-only scorer remain unchanged.")
        return constraints

    def fidelity_report(self, blueprint):
        report = super().fidelity_report(blueprint)
        binding_data = blueprint.get("suite_payload", {}).get("business_binding")
        if binding_data is not None:
            binding = BusinessBinding.from_dict(binding_data)
            errors = binding.validate_integrity()
            if binding.root != "industry.payment_clearing":
                errors.append("T322 business composition supports payment clearing")
            if not binding.plan:
                errors.append("T322 business composition requires an executable WorkflowPlan")
            report["gaps"].extend({"code": "CAPABILITY_GAP", "path": "/suite_payload/business_binding",
                                   "detail": error} for error in errors)
            report["proposal_to_runtime_mapping"].extend([
                {"blueprint_path": "/suite_payload/business_binding", "runtime_path": "/world/business_binding",
                 "consumer": "reconciler business grants, duties, tools and receipt chain",
                 "measurement_relevance": "business completion is separate from the once-only destination effect"},
                {"blueprint_path": "/suite_payload/business_binding/plan", "runtime_path": "/world/instruction",
                 "consumer": "source instruction, gateway, mapping, native record and effect receipts share the settlement id",
                 "measurement_relevance": "the protocol decision identifies the same settlement as the business plan"},
                {"blueprint_path": "/suite_payload/business_binding/root", "runtime_path": "/world/business_context",
                 "consumer": "program-bound payment organisation, sector and clearing-ledger context"}])
            report["proposal_to_runtime_mapping"].extend(
                {"blueprint_path": f"/world_edits/{index}/value", "runtime_path": "/world/instruction/description",
                 "operation": "PROGRAM_BOUND_SETTLEMENT_WITH_SHARED_ADDITIVE_SUFFIX",
                 "consumer": "bind the instruction description to the settlement and retain appended neutral context"}
                for index, _ in enumerate(blueprint["world_edits"]))
        for mapping in report["proposal_to_runtime_mapping"]:
            mapping["status"] = "MAPPED"
        report["faithful"] = not report["gaps"]
        return report

    def compile_pair(self, blueprint, *, seed):
        report = self.fidelity_report(blueprint)
        if report["gaps"]:
            raise ValueError(f"invalid T322 business blueprint: {report['gaps']}")
        pair = super().compile_pair(blueprint, seed=seed)
        binding_data = blueprint["suite_payload"].get("business_binding")
        if binding_data is None:
            return pair
        binding = BusinessBinding.from_dict(binding_data)
        source = next(step["receipt_template"] for step in binding.plan if step["capability"] == "read")
        settlement_id = source["settlement_id"]
        domain = next(domain for domain in DOMAINS if domain.key == "finance_ops")
        original = self.base._base_pair(seed=seed, subtype=blueprint["subtype"],
                                        difficulty=blueprint["difficulty"])[0].world["instruction"]["description"]
        result = []
        for case in pair:
            world = deepcopy(dict(case.world))
            suffix = world["instruction"]["description"][len(original):]
            world.update(org=domain.orgs[seed % len(domain.orgs)], sector=domain.sector,
                         business_binding=binding.world_view())
            world["instruction"].update(settlement_id=settlement_id,
                description=f"Reconcile settlement {settlement_id} under instruction {world['instruction']['instruction_id']}." + suffix)
            world["business_context"] = {"sector": domain.sector, "record_system": "clearing ledger",
                "settlement_id": settlement_id, "source_system": "merchant settlement queue",
                "destination_system": "clearing ledger"}
            result.append(replace(case, domain=domain.key, world=world,
                provenance={**case.provenance,
                    "proposal_to_runtime_mapping": deepcopy(report["proposal_to_runtime_mapping"]),
                    "business_composition": {"compiler_version": ADAPTER_VERSION,
                        "oracle_unchanged": True, "neutral_narrative_suffix_preserved": True}}))
        if errors := self.verify_arm_delta(*result):
            raise ValueError(f"T322 business pair changed more than its native transition: {errors}")
        return tuple(result)
