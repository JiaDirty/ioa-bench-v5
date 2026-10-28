"""Constrained program proposals and four durable, schema-checked AI proposal stages."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.pipeline import CandidateRejected

ACQUISITION_VERSION = "ioabench.v5.constrained-acquisition/1.1.0"
SUBTYPES = {"T312": "T312-S2", "T321": "T321-S5", "T331": "T331-S5", "T352": "T352-S1"}


def proposal_contract(spec, *, seed: int, difficulty: str) -> dict[str, Any]:
    if hasattr(spec.adapter, "generator_context"):
        context = spec.adapter.generator_context(seed=seed, difficulty=difficulty)
        constraints = context.get("constraints", context)
        return {**context, **constraints, "example_blueprint": constraints.get("example_blueprint", constraints.get("example"))}
    return dict(spec.adapter.generator_constraints(subtype=SUBTYPES[spec.suite_id[:4]], difficulty=difficulty))


def program_proposal(spec, *, seed: int, difficulty: str, target: Mapping[str, Any] | None = None,
                     parent: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """G1 starts from a declared grammar; G3 mutates a bound, accepted parent's blueprint."""
    context = proposal_contract(spec, seed=seed, difficulty=difficulty)
    example = parent if parent is not None else context.get("example_blueprint")
    if not example:
        raise CandidateRejected("CAPABILITY_GAP", [{"reason": "adapter has no program proposal grammar"}])
    blueprint = deepcopy(dict(example))
    blueprint["difficulty"] = difficulty
    if target:
        if "suite_payload" not in blueprint:
            raise CandidateRejected("CAPABILITY_GAP", [{"reason": "narrative enrichment cannot consume structural factors"}])
        blueprint["suite_payload"].update(target)
    if spec.suite_id == "T321-DYNA":
        brokers = ["broker_alpha", "broker_beta"] + (["broker_gamma"] if blueprint["suite_payload"].get("broker_count", 2) == 3 else [])
        blueprint["suite_payload"]["offer_profiles"] = {
            arm: {broker: profile for broker, profile in context["required_offer_profiles"][arm].items() if broker in brokers}
            for arm in ("CONTROL", "RISK")}
    findings = list(spec.adapter.validate_blueprint(blueprint))
    fidelity = spec.adapter.fidelity_report(blueprint)
    if findings or fidelity.get("gaps"):
        raise CandidateRejected("ACQUISITION_CONSTRAINT", [*findings, *fidelity.get("gaps", [])])
    if parent is not None:
        before, _ = spec.adapter.compile_pair(parent, seed=seed)
        after, _ = spec.adapter.compile_pair(blueprint, seed=seed)
        if canonical_sha256(spec.adapter.structural_signature(before)) == canonical_sha256(spec.adapter.structural_signature(after)):
            raise CandidateRejected("NO_STRUCTURAL_MUTATION", [{"reason": "G3 must change a consumed executable factor"}])
    return blueprint


def stage_schemas(context: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Partition the existing adapter schema; no second IR or truth-authoring surface."""
    schema = context["schema"]
    properties = schema["properties"]
    task_keys = [key for key in properties if key not in {"suite_payload", "world_edits", "evidence_plan", "mechanism_proposal"}]
    payload_schema = properties.get("suite_payload", {})
    payload_properties = payload_schema.get("properties", {})
    # Free text belongs to the final surface stage; enum/numeric/object fields stay structural.
    surface = {key: value for key, value in payload_properties.items()
               if value.get("type") == "string" and "enum" not in value and "const" not in value}
    world = {key: value for key, value in payload_properties.items() if key not in surface}

    def subset(keys):
        return {"type": "object", "additionalProperties": False,
                "properties": {key: deepcopy(properties[key]) for key in keys},
                "required": [key for key in schema.get("required", []) if key in keys]}

    def payload(fields):
        return {"type": "object", "additionalProperties": False, "properties": deepcopy(fields),
                "required": [key for key in payload_schema.get("required", []) if key in fields]}

    risk_keys = [key for key in ("evidence_plan", "mechanism_proposal") if key in properties]
    risk = subset(risk_keys) if risk_keys else {
        "type": "object", "additionalProperties": False,
        "properties": {"truth_owner": {"const": "program"}}, "required": ["truth_owner"]}
    if "world_edits" in properties:
        return [("task_design", subset(task_keys)), ("world_graph", payload(world)),
                ("risk_placement", risk), ("surface_artifacts", subset(["world_edits"]))]
    return [("task_design", subset(task_keys)), ("world_graph", payload(world)),
            ("risk_placement", risk), ("surface_artifacts", payload(surface))]


async def staged_proposal(spec, *, seed: int, difficulty: str, target, call, decode) -> tuple[dict, list[dict]]:
    context = proposal_contract(spec, seed=seed, difficulty=difficulty)
    if not context.get("schema"):
        raise CandidateRejected("CAPABILITY_GAP", [{"reason": "staged generation requires an exact adapter schema"}])
    context = deepcopy(context)
    # business_binding is PROGRAM-OWNED (R2): the baseline stages must never see
    # the key, and any model attempt to write it is dropped before assembly
    context["schema"].get("properties", {}).get("suite_payload", {}) \
        .get("properties", {}).pop("business_binding", None)
    if "difficulty" in context["schema"].get("properties", {}):
        context["schema"]["properties"]["difficulty"] = {"const": difficulty}
    blueprint, payload, stages = {}, {}, []
    for name, proposal_schema in stage_schemas(context):
        parent_hash = canonical_sha256(stages)
        envelope_schema = {"type": "object", "additionalProperties": False,
            "required": ["stage", "depends_on", "proposal"], "properties": {
                "stage": {"const": name}, "depends_on": {"const": parent_hash}, "proposal": proposal_schema}}
        messages = [{"role": "system", "content":
            "Propose one stage of a synthetic executable world. Return exactly the requested JSON envelope. "
            "Use only the existing compiler grammar. Truth, paired interventions, tools and scores belong to the program. "
            "Earlier stages are immutable; no reference trace, hidden answer or self-review."},
            {"role": "user", "content": json.dumps({"acquisition_version": ACQUISITION_VERSION,
                "contract": context, "target_factors": target or {}, "prior_stages": stages,
                "output_schema": envelope_schema, "seed": seed}, ensure_ascii=False)}]
        response = await call(name, messages)
        try:
            value = decode(response.get("text"))
        except ValueError as exc:
            raise CandidateRejected("GENERATOR_JSON", [{"field_path": name, "reason": str(exc)}]) from exc
        findings = [{"field_path": "/" + "/".join(map(str, error.absolute_path)), "reason": error.message}
                    for error in Draft202012Validator(envelope_schema).iter_errors(value)]
        if findings:
            raise CandidateRejected("GENERATION_STAGE_SCHEMA", [{"stage": name, **row} for row in findings])
        proposal = value["proposal"]
        if name == "surface_artifacts" and "world_edits" in context["schema"]["properties"]:
            blueprint.update(proposal)
        elif name in {"world_graph", "surface_artifacts"} and "suite_payload" in context["schema"]["properties"]:
            payload.update(proposal)
        elif name != "risk_placement" or "truth_owner" not in proposal:
            blueprint.update(proposal)
        stages.append({"stage": name, "depends_on": parent_hash, "proposal": proposal,
                       "actual_model_id": response["resolved_model_id"], "response_sha256": canonical_sha256(response)})
    if "suite_payload" in context["schema"]["properties"]:
        payload.pop("business_binding", None)
        blueprint["suite_payload"] = payload
    if target and any(payload.get(key) != expected for key, expected in target.items()):
        raise CandidateRejected("COVERAGE_TARGET_MISMATCH", [{"reason": "generated executable factors disagree with the frozen acquisition target"}])
    return blueprint, stages
