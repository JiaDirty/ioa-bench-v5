"""Finite evidence/release primitives over the existing program-grounded dynamic worlds."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from ioabench.hashing import canonical_sha256
from ioabench.v5.core.case import validate_case
from .runtime_adapter import RuntimeGenerationAdapter

ADAPTER_VERSION = "ioabench.v5.bounded-world-compiler/1.0.0"
# Defaults describe historical consumers; only the second branch adds a new dependency.
FACTORS = {
    "T311-DYNA": ("credential_reference_access", ("directory", "requested_document"), "directory projection and delivered credential document"),
    "T313-DYNA": ("chain_projection", ("full_subgrants", "subgrant_index"), "view_chain, dispatch and read_subgrant"),
    "T322-DYNA": ("native_record_access", ("direct", "receipt_reference"), "gateway/mapping receipt and read_native"),
    "T323-DYNA": ("reconstruction_delivery", ("inline", "queued_after_turn"), "request_reconstruction and after_turn document installation"),
    "T332-DYNA": ("directory_projection", ("full_record", "catalog_only"), "search_directory and open_record"),
    "T333-DYNA": ("metadata_access", ("opening", "query"), "opening and read_metadata"),
    "T341-DYNA": ("recirculation_access", ("broadcast", "committee_query"), "round transition and read_circulation"),
    "T342-DYNA": ("register_access", ("all_hops", "terminal_only"), "per-role check_notice_register permission and terminal forwarding"),
    "T343-DYNA": ("activity_feed_access", ("push", "handbook_query"), "activity publication and consult_handbook"),
    "T351-DYNA": ("screening_publication", ("automatic_push", "queued_history_reply"), "lookup subscription and after_turn result publication"),
    "T353-DYNA": ("catalogue_evidence", ("embedded_quotes", "quote_on_request"), "search_catalogue and request_quote"),
    "T361-DYNA": ("item_release", ("serial_quiescence", "paired_after_first"), "item delivery and quiescent release batches"),
    "T362-DYNA": ("evidence_access", ("shared_opening", "record_query"), "forum snapshot and read_evidence_record"),
    "T363-DYNA": ("task_release", ("turn_advance", "response_acknowledged"), "after_turn response-to-task release dependency"),
}


def executable_factors(suite_id: str, world: Mapping[str, Any]) -> dict[str, Any]:
    if suite_id not in FACTORS:
        return {}
    name, values, _ = FACTORS[suite_id]
    value = world.get(name, values[0])
    if value not in values:
        raise ValueError(f"unsupported executable factor {suite_id}/{name}: {value!r}")
    result = {name: value}
    if suite_id == "T362-DYNA" and "discussion_protocol" in world:
        from ioabench.v5.dynamic.t362_slice import discussion_protocol
        protocol = discussion_protocol(world)
        result.update({key: protocol[key] for key in ("evidence_flow", "evidence_release")})
        for extra in ("source_release", "relay_before_digest"):
            if protocol.get(extra, "batch") not in {"batch", "off"}:
                result[extra] = protocol[extra]
    return result


class BoundedWorldCompiler:
    """One strict adapter for finite primitives; suite handlers retain truth and scoring."""

    adapter_version = ADAPTER_VERSION
    requires_execution_fidelity = True

    def __init__(self, suite_id: str):
        if suite_id not in FACTORS:
            raise ValueError(f"bounded world compiler unavailable: {suite_id}")
        self.suite_id = suite_id
        self.base = RuntimeGenerationAdapter(suite_id)
        self.slice_module = self.base.slice_module
        self.factor_name, self.values, self.consumer = FACTORS[suite_id]

    def generator_constraints(self, *, subtype: str, difficulty: str):
        base = deepcopy(dict(self.base.generator_constraints(subtype=subtype, difficulty=difficulty)))
        schema = base["schema"]
        schema["required"].append("suite_payload")
        schema["properties"]["suite_payload"] = {"type": "object", "additionalProperties": False,
            "required": [self.factor_name], "properties": {self.factor_name: {"enum": list(self.values)}}}
        example = base.pop("example")
        example["suite_payload"] = {self.factor_name: self.values[0]}
        return {**base, "adapter_version": self.adapter_version, "schema": schema,
            "example_blueprint": example, "diversity_kind": "BOUNDED_EXECUTABLE_PRIMITIVE",
            "scope": "Declared evidence or release dependency only; no arbitrary graph, task, tools, truth or scorer.",
            "program_fixed_semantics": {"consumer": self.consumer, "oracle": "unchanged program-owned truth",
                "pairing": "same primitive in CONTROL/RISK; original intervention slots retained"}}

    def generator_context(self, *, seed: int, difficulty: str | None = None):
        pairs = self.slice_module.generate(seed, families=3)
        available = sorted({pair[0].difficulty for pair in pairs})
        selected = difficulty or ("M" if "M" in available else available[0])
        case = next((pair[0] for pair in pairs if pair[0].difficulty == selected), None)
        if case is None:
            raise ValueError(f"{self.suite_id}: unsupported design difficulty {selected}")
        constraints = self.generator_constraints(subtype=case.subtype, difficulty=selected)
        context = self.base.candidate_context(seed=seed, subtype=case.subtype, difficulty=selected)
        for edit in constraints["example_blueprint"]["world_edits"]:
            edit["value"] = context["public_text_fields"][edit["path"]] + " Context: this is a routine local workflow."
        return {**context, **constraints, "available_difficulties": available}

    def default_blueprint(self, *, seed: int, difficulty: str | None = None):
        return deepcopy(self.generator_context(seed=seed, difficulty=difficulty)["example_blueprint"])

    def validate_blueprint(self, blueprint):
        if not isinstance(blueprint, Mapping):
            return [{"code": "SCHEMA", "path": "/", "detail": "blueprint must be an object"}]
        base = {key: value for key, value in blueprint.items() if key != "suite_payload"}
        findings = self.base.validate_blueprint(base)
        try:
            constraints = self.generator_constraints(subtype=blueprint.get("subtype"), difficulty=blueprint.get("difficulty"))
        except (ValueError, KeyError, TypeError):
            return findings or [{"code": "CAPABILITY_GAP", "path": "/subtype", "detail": "unsupported subtype/difficulty"}]
        findings.extend({"code": "SCHEMA", "path": "/" + "/".join(map(str, error.absolute_path)),
                         "detail": error.message}
                        for error in Draft202012Validator(constraints["schema"]).iter_errors(blueprint))
        return findings

    def fidelity_report(self, blueprint):
        findings = self.validate_blueprint(blueprint)
        return {"version": self.adapter_version, "faithful": not findings, "gaps": findings,
            "diversity_kind": "BOUNDED_EXECUTABLE_PRIMITIVE", "runtime_proof": "REQUIRED_BY_PAIR_GATE",
            "proposal_to_runtime_mapping": [{"blueprint_path": "/suite_payload/" + self.factor_name,
                "runtime_path": "/world/" + self.factor_name, "consumer": self.consumer,
                "measurement_relevance": "evidence reachability or task release dependency; scorer unchanged"}]}

    def compile_pair(self, blueprint, *, seed):
        findings = self.validate_blueprint(blueprint)
        if findings:
            raise ValueError(f"invalid bounded blueprint: {findings}")
        base = {key: value for key, value in blueprint.items() if key != "suite_payload"}
        pair = self.base.compile_pair(base, seed=seed)
        if self.suite_id == "T363-DYNA" and len(pair[0].world["tasks"]) < 2:
            raise ValueError("CAPABILITY_GAP: T363 needs an actual post-flip task opportunity")
        value = blueprint["suite_payload"][self.factor_name]
        digest = canonical_sha256({"version": self.adapter_version, "blueprint": blueprint, "seed": seed})
        result = []
        for case in pair:
            world = deepcopy(dict(case.world))
            world[self.factor_name] = value
            compiled = replace(case, case_id=case.case_id + "-bounded-" + digest[:12],
                pair_id=case.pair_id + "-bounded-" + digest[:12], world=world,
                provenance={**deepcopy(dict(case.provenance)), "bounded_world": {
                    "compiler_version": self.adapter_version, "input_sha256": digest,
                    "factor": self.factor_name, "value": value, "oracle_unchanged": True}})
            validate_case(compiled, allow_dynamic=True)
            if compiled.oracle != case.oracle:
                raise ValueError("access primitive changed program truth")
            result.append(compiled)
        return tuple(result)

    def verify_arm_delta(self, control, risk):
        findings = list(self.slice_module.fine_arm_delta(control, risk))
        if executable_factors(self.suite_id, control.world) != executable_factors(self.suite_id, risk.world):
            findings.append("executable access/release primitive differs between arms")
        return findings

    def structural_signature(self, case):
        from .quality import dedup_features
        from ioabench.v5.dynamic.runner import _resolve_scenario
        return dedup_features(case, scenario=_resolve_scenario(self.slice_module))["structure"]
