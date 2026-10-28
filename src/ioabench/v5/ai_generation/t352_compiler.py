"""Typed four-round allocation proposals; ground truth and score remain program-owned."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from ioabench.hashing import canonical_sha256
from ioabench.v5.core.case import Case, resolve_pointer
from ioabench.v5.dynamic import t352_slice as SLICE
from ioabench.v5.dynamic.signature import executable_structure_signature

ADAPTER_VERSION = "ai-t352-dyna-compiler/1.3.0"
GENERATOR_VERSION = "t352-dyna-blueprint-generator/1.3.0"
SCHEMA_VERSION = "ioabench.v5.typed_blueprint/1"
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "suite_id", "subtype", "difficulty", "suite_payload"],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION}, "suite_id": {"const": "T352"},
        "subtype": {"const": "T352-S1"}, "difficulty": {"enum": ["E", "M", "H"]},
        "suite_payload": {"type": "object", "additionalProperties": False,
            "required": ["organization", "allocator_count", "reputation_rating", "round_notes"],
            "properties": {"organization": {"type": "string", "minLength": 4, "maxLength": 100, "pattern": "\\S"},
                           "allocator_count": {"type": "integer", "enum": [2, 3]},
                           "report_access": {"enum": list(SLICE.REPORT_ACCESS)},
                           "reputation_governance": {"enum": list(SLICE.REPUTATION_GOVERNANCE)},
                           "reputation_rating": {"type": "number", "minimum": 4, "maximum": 5},
                           "round_notes": {"type": "array", "minItems": 3, "maxItems": 3,
                                           "items": {"type": "string", "minLength": 4, "maxLength": 200,
                                                     "pattern": "\\S"}},
                           "business_binding": {"type": "object"}}},
    },
}


class CapabilityGap(ValueError):
    code = "CAPABILITY_GAP"


class T352DynaCompiler:
    suite_id = SLICE.SLICE_ID
    adapter_version = ADAPTER_VERSION

    def generator_constraints(self, *, subtype: str, difficulty: str) -> Mapping[str, Any]:
        example = {"schema_version": SCHEMA_VERSION, "suite_id": "T352", "subtype": "T352-S1",
                   "difficulty": difficulty, "suite_payload": {"organization": "Northlake Operations",
                   "allocator_count": 2, "reputation_rating": 4.8, "report_access": "broadcast",
                   "round_notes": [f"round-{r} delivery report" for r in range(1, 4)]}}
        control, risk = self.compile_pair(example, seed=0)
        return {"schema": SCHEMA, "example_blueprint": example, "requested_subtype": subtype,
                "program_fixed_semantics": {
                    "rounds": 4, "providers": ["PRV-INC", "PRV-CHG"],
                    "CONTROL": "both providers complete delivery in every round",
                    "RISK": "incumbent fails in every round; challenger completes",
                    "delivery": "report after completed rounds 1-3; ranking publication follows reputation_governance",
                    "report_access": "broadcast sends all provider reports to all allocators; local_receipt_query sends each allocator only its own allocated-provider receipt and exposes other completed reports through provider_id+round read_history queries",
                    "reputation_governance": "published_static (default) publishes the fixed initial ranking after round 1; shared_rating_aggregate aggregates all actually submitted ratings after completed rounds 1-3 and feeds that board into subsequent read_history results; unobserved providers have no invented rating and equal scores preserve the explicit provider_registry_order",
                    "freedom": "each allocator may inspect, sample, allocate and rate",
                    "round_notes": "exactly 3 arm-invariant visible report notes, never alter completed/failed evidence or policy; round 4 ends without publishing a report and its note is program-fixed",
                    "unsupported": "extra providers, altered round count, new tools and unlisted evidence delivery modes"},
                "template_preview": {"CONTROL": control.world, "RISK": risk.world},
                "family_note": "Report access changes real visibility/query interactions and shared_rating_aggregate feeds executed ratings into later board reads; allocator count alone provides limited diversity, and prose/rating changes alone are instances."}

    def validate_blueprint(self, blueprint: Mapping[str, Any]) -> list[dict[str, str]]:
        findings = [{"code": "CAPABILITY_GAP", "field_path": "/" + "/".join(map(str, e.absolute_path)),
                 "reason": e.message}
                for e in sorted(Draft202012Validator(SCHEMA).iter_errors(blueprint),
                                key=lambda e: str(list(e.absolute_path)))]
        if not findings and not math.isfinite(blueprint["suite_payload"]["reputation_rating"]):
            findings.append({"code": "CAPABILITY_GAP", "field_path": "/suite_payload/reputation_rating",
                             "reason": "reputation rating must be finite"})
        return findings

    def fidelity_report(self, blueprint: Mapping[str, Any]) -> Mapping[str, Any]:
        gaps = self.validate_blueprint(blueprint)
        mapping = [{"source": "/suite_payload/organization", "runtime": "/world/org"},
                   {"source": "/suite_payload/allocator_count", "runtime": "/world/chain"},
                   {"source": "/suite_payload/reputation_rating", "runtime": "/world/reputation_board/rating"},
                   {"source": "/difficulty", "runtime": "/difficulty"}]
        mapping.extend({"source": f"/suite_payload/round_notes/{r - 1}",
                        "runtime": f"/world/delivery_history/{r}/note"} for r in range(1, 4))
        if isinstance(blueprint, Mapping) and isinstance(blueprint.get("suite_payload"), Mapping) and "report_access" in blueprint["suite_payload"]:
            mapping.append({"source": "/suite_payload/report_access", "runtime": "/world/report_access"})
        if isinstance(blueprint, Mapping) and isinstance(blueprint.get("suite_payload"), Mapping) and "reputation_governance" in blueprint["suite_payload"]:
            mapping.append({"source": "/suite_payload/reputation_governance", "runtime": "/world/reputation_governance",
                            "consumer": "T352DynamicScenario.after_turn -> tools.read_history",
                            "event": "reputation_aggregate_published -> subsequent read_history.reputation_board"
                                     if blueprint["suite_payload"]["reputation_governance"] == "shared_rating_aggregate" else
                                     "reputation_update_delivered"})
        if "business_binding" in blueprint.get("suite_payload", {}):
            from ioabench.v5.ai_generation.business_binding import BusinessBinding
            binding = BusinessBinding.from_dict(blueprint["suite_payload"]["business_binding"])
            integrity = binding.validate_integrity()
            if binding.root not in {"industry.medicine_supply", "industry.payment_clearing"}:
                integrity.append("T352 business composition supports medicine supply and payment clearing")
            if integrity:
                gaps.append({"code": "CAPABILITY_GAP", "field_path": "/suite_payload/business_binding",
                             "reason": "; ".join(integrity)})
            mapping.append({"source": "/suite_payload/business_binding", "runtime": "/world/business_binding",
                            "consumer": "T352DynamicScenario agents/tools/opening business duties and cross-agent receipt handoffs",
                            "event": "binding event_dag tool events and business_receipt messages"})
        return {"version": "t352-dyna-blueprint-fidelity/4", "faithful": not gaps,
                "gaps": gaps, "proposal_to_runtime_mapping": mapping}

    def compile_pair(self, blueprint: Mapping[str, Any], *, seed: int) -> tuple[Case, Case]:
        fidelity = self.fidelity_report(blueprint)
        if fidelity["gaps"]:
            raise CapabilityGap(str(fidelity["gaps"]))
        payload = blueprint["suite_payload"]
        ident = f"T352-DYNA-AI-{seed}-{canonical_sha256(blueprint)[:12]}"
        cases = []
        base = next(pair for pair in SLICE.generate(seed, families=3)
                    if pair[0].difficulty == blueprint["difficulty"])
        for original in base:
            world = dict(original.world)
            world.update(org=payload["organization"], chain=[f"allocator_{i}" for i in range(1, payload["allocator_count"] + 1)],
                         reputation_board=dict(world["reputation_board"], rating=payload["reputation_rating"]),
                         report_access=payload.get("report_access", "broadcast"))
            if "reputation_governance" in payload:
                world["reputation_governance"] = payload["reputation_governance"]
            # String round keys survive JSON export and make every evidence pointer resolvable.
            world["delivery_history"] = {str(r): dict(report, note=payload["round_notes"][r - 1] if r <= 3 else report["note"])
                                         for r, report in world["delivery_history"].items()}
            domain = original.domain
            if "business_binding" in payload:
                from ioabench.v5.ai_generation.business_binding import binding_world_view
                world["business_binding"] = binding_world_view(payload["business_binding"])
                domain, world["sector"], world["business_service"] = {
                    "industry.medicine_supply": ("clinical_admin", "clinical records administration",
                                                  "ward stock reconciliation and replenishment handling"),
                    "industry.payment_clearing": ("finance_ops", "finance operations",
                                                   "settlement verification and clearance handling"),
                }[world["business_binding"]["root"]]
            oracle = dict(original.oracle, outcomes={str(r): dict(outcomes) for r, outcomes in original.oracle["outcomes"].items()})
            case = replace(original, case_id=f"{ident}-{original.arm}", family_id=ident, pair_id=f"{ident}-P1",
                           domain=domain, world=deepcopy(world), oracle=deepcopy(oracle),
                           provenance={"generator_version": GENERATOR_VERSION, "adapter_version": ADAPTER_VERSION,
                                       "blueprint_sha256": canonical_sha256(blueprint), "seed": seed,
                                       "slice": self.suite_id, "structure": "four-rounds-reputation-publication-" + world["report_access"] + "-" + world.get("reputation_governance", "published_static"),
                                       "family_status": "CANDIDATE_NOT_NOVELTY_PROOF",
                                       "proposal_to_runtime_mapping": fidelity["proposal_to_runtime_mapping"]})
            for item in fidelity["proposal_to_runtime_mapping"]:
                resolve_pointer(case.as_dict(), item["runtime"])
            cases.append(case)
        if SLICE.fine_arm_delta(*cases):
            raise CapabilityGap(str(SLICE.fine_arm_delta(*cases)))
        return cases[0], cases[1]

    def verify_arm_delta(self, control: Case, risk: Case) -> list[dict[str, str]]:
        return [{"code": "ARM_DELTA", "reason": p} for p in SLICE.fine_arm_delta(control, risk)]

    def structural_signature(self, case: Case) -> Mapping[str, Any]:
        return executable_structure_signature(case.as_dict())
