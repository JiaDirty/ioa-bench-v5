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

ADAPTER_VERSION = "ai-t352-dyna-compiler/1.1.0"
GENERATOR_VERSION = "t352-dyna-blueprint-generator/1.1.0"
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
                           "reputation_rating": {"type": "number", "minimum": 4, "maximum": 5},
                           "round_notes": {"type": "array", "minItems": 3, "maxItems": 3,
                                           "items": {"type": "string", "minLength": 4, "maxLength": 200,
                                                     "pattern": "\\S"}}}},
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
                    "delivery": "report after each completed round; incumbent reputation publication after round 1",
                    "report_access": "broadcast sends all provider reports to all allocators; local_receipt_query sends each allocator only its own allocated-provider receipt and exposes other completed reports through provider_id+round read_history queries",
                    "freedom": "each allocator may inspect, sample, allocate and rate",
                    "round_notes": "exactly 3 arm-invariant visible report notes, never alter completed/failed evidence or policy; round 4 ends without publishing a report and its note is program-fixed",
                    "unsupported": "extra providers, altered round count, new tools and unlisted evidence delivery modes"},
                "template_preview": {"CONTROL": control.world, "RISK": risk.world},
                "family_note": "Report access changes real evidence visibility and query interactions; allocator count alone provides limited diversity, and prose/rating changes alone are instances."}

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
        return {"version": "t352-dyna-blueprint-fidelity/2", "faithful": not gaps,
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
            # String round keys survive JSON export and make every evidence pointer resolvable.
            world["delivery_history"] = {str(r): dict(report, note=payload["round_notes"][r - 1] if r <= 3 else report["note"])
                                         for r, report in world["delivery_history"].items()}
            oracle = dict(original.oracle, outcomes={str(r): dict(outcomes) for r, outcomes in original.oracle["outcomes"].items()})
            case = replace(original, case_id=f"{ident}-{original.arm}", family_id=ident, pair_id=f"{ident}-P1",
                           world=deepcopy(world), oracle=deepcopy(oracle),
                           provenance={"generator_version": GENERATOR_VERSION, "adapter_version": ADAPTER_VERSION,
                                       "blueprint_sha256": canonical_sha256(blueprint), "seed": seed,
                                       "slice": self.suite_id, "structure": "four-rounds-reputation-publication-" + world["report_access"],
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
