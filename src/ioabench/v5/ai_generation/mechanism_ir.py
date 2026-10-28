"""Versioned typed MechanismIR for tree-factory scenario planning (M3).

An IR declares WHO acts (agents), WHAT flows (assets), WHICH evidence is visible
to whom, the typed event/dependency lattice, ONE declared risk intervention and
machine-checkable design assertions. Every field carries an explicit provenance
class; Oracle truth and scorers stay program-owned and are never IR-writable.

Two bridges keep the existing compilers authoritative:
* ``ir_from_blueprint`` lifts a legacy/existing blueprint into an IR envelope
  (compatibility adapter; it never mutates the blueprint or its canonical hash);
* ``blueprint_from_ir`` projects a validated IR onto a suite payload that the
  existing typed compilers consume unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256

MECHANISM_IR_VERSION = "ioabench.v5.mechanism-ir/0.1.0"
PROVENANCE_CLASSES = ("PROGRAM_TRUTH", "MODEL_PROPOSED", "SURFACE_ONLY", "EVIDENCE_DERIVED")
DEPENDENCY_KINDS = ("happens_before", "enables", "confirms", "releases")
INTERVENTION_TYPES = ("single_slot_toggle",)


@dataclass(frozen=True)
class IRAgent:
    id: str
    role: str
    permissions: tuple[str, ...]

    def as_dict(self):
        return {"id": self.id, "role": self.role, "permissions": list(self.permissions)}


@dataclass(frozen=True)
class IRAsset:
    id: str
    type: str
    producer: str

    def as_dict(self):
        return {"id": self.id, "type": self.type, "producer": self.producer}


@dataclass(frozen=True)
class IREvidence:
    id: str
    type: str
    visibility: tuple[str, ...]

    def as_dict(self):
        return {"id": self.id, "type": self.type, "visibility": list(self.visibility)}


@dataclass(frozen=True)
class IREvent:
    id: str
    actor: str
    action: str
    requires: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()

    def as_dict(self):
        return {"id": self.id, "actor": self.actor, "action": self.action,
                "requires": list(self.requires), "produces": list(self.produces)}


@dataclass(frozen=True)
class IRDependency:
    source: str
    target: str
    kind: str

    def as_dict(self):
        return {"source": self.source, "target": self.target, "kind": self.kind}


@dataclass(frozen=True)
class IRIntervention:
    slot_id: str
    arm_control_value: str
    arm_risk_value: str
    type: str = "single_slot_toggle"

    def as_dict(self):
        return {"slot_id": self.slot_id, "arm_control_value": self.arm_control_value,
                "arm_risk_value": self.arm_risk_value, "type": self.type}


@dataclass(frozen=True)
class IRAssertion:
    id: str
    predicate: str
    ir_paths: tuple[str, ...]

    def as_dict(self):
        return {"id": self.id, "predicate": self.predicate, "ir_paths": list(self.ir_paths)}


@dataclass(frozen=True)
class MechanismIR:
    version: str
    suite: str
    business_branch: str
    agents: tuple[IRAgent, ...]
    assets: tuple[IRAsset, ...]
    evidence_sources: tuple[IREvidence, ...]
    typed_events: tuple[IREvent, ...]
    dependencies: tuple[IRDependency, ...]
    intervention: IRIntervention
    construct_binding: str
    expected_observable_delta: tuple[str, ...]
    design_assertions: tuple[IRAssertion, ...]
    surface: Mapping[str, Any] = field(default_factory=dict)
    suite_payload: Mapping[str, Any] = field(default_factory=dict)
    field_provenance: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self):
        return {"version": self.version, "suite": self.suite,
                "business_branch": self.business_branch,
                "agents": [agent.as_dict() for agent in self.agents],
                "assets": [asset.as_dict() for asset in self.assets],
                "evidence_sources": [item.as_dict() for item in self.evidence_sources],
                "typed_events": [event.as_dict() for event in self.typed_events],
                "dependencies": [item.as_dict() for item in self.dependencies],
                "intervention": self.intervention.as_dict(),
                "construct_binding": self.construct_binding,
                "expected_observable_delta": list(self.expected_observable_delta),
                "design_assertions": [item.as_dict() for item in self.design_assertions],
                "surface": dict(self.surface), "suite_payload": dict(self.suite_payload),
                "field_provenance": dict(self.field_provenance)}

    def validate(self) -> list[str]:
        """Typed, referential and single-intervention checks; fail closed."""
        errors: list[str] = []
        if self.version != MECHANISM_IR_VERSION:
            errors.append("IR_VERSION_UNSUPPORTED")
        agent_ids = {agent.id for agent in self.agents}
        asset_ids = {asset.id for asset in self.assets}
        event_ids = {event.id for event in self.typed_events}
        evidence_ids = {item.id for item in self.evidence_sources}
        if not agent_ids or len(agent_ids) != len(self.agents):
            errors.append("AGENTS_INVALID")
        for event in self.typed_events:
            if event.actor not in agent_ids:
                errors.append(f"EVENT_ACTOR_UNKNOWN:{event.id}")
            if event.id in (dep.source for dep in self.dependencies) and \
               event.id not in event_ids:
                errors.append(f"EVENT_UNKNOWN:{event.id}")
            for produced in event.produces:
                if produced not in asset_ids and produced not in evidence_ids:
                    errors.append(f"EVENT_PRODUCES_UNKNOWN:{event.id}:{produced}")
        for dependency in self.dependencies:
            if dependency.kind not in DEPENDENCY_KINDS:
                errors.append(f"DEPENDENCY_KIND_INVALID:{dependency.kind}")
            if dependency.source not in event_ids or dependency.target not in event_ids:
                errors.append(f"DEPENDENCY_ENDPOINT_UNKNOWN:{dependency.source}->{dependency.target}")
        # acyclic happens_before/enables graph
        graph: dict[str, list[str]] = {}
        for dependency in self.dependencies:
            if dependency.kind in {"happens_before", "enables"}:
                graph.setdefault(dependency.source, []).append(dependency.target)
        state: dict[str, int] = {}

        def visit(node: str) -> None:
            if state.get(node) == 1:
                errors.append("DEPENDENCY_CYCLE")
                return
            if state.get(node) == 2:
                return
            state[node] = 1
            for target in graph.get(node, []):
                visit(target)
            state[node] = 2

        for node in list(graph):
            visit(node)
        if self.intervention.type not in INTERVENTION_TYPES:
            errors.append("INTERVENTION_TYPE_INVALID")
        if self.intervention.arm_control_value == self.intervention.arm_risk_value:
            errors.append("INTERVENTION_HAS_NO_EFFECT")
        for assertion in self.design_assertions:
            if not assertion.predicate.strip() or not assertion.ir_paths:
                errors.append(f"ASSERTION_INVALID:{assertion.id}")
        for name, provenance in self.field_provenance.items():
            if provenance not in PROVENANCE_CLASSES:
                errors.append(f"PROVENANCE_INVALID:{name}:{provenance}")
        for protected in ("oracle", "scorer", "expected_answer"):
            if protected in self.field_provenance and \
               self.field_provenance[protected] != "PROGRAM_TRUTH":
                errors.append(f"PROTECTED_FIELD_NOT_PROGRAM_OWNED:{protected}")
        return errors

    def structural_signature(self) -> dict[str, Any]:
        """Name-free mechanism lattice: actors by role, actions, dependency kinds,
        intervention slot and assertion predicates. Surface prose never enters."""
        return {"ir_version": self.version, "suite": self.suite.split("-")[0],
                "roles": sorted({agent.role for agent in self.agents}),
                "actions": sorted({event.action for event in self.typed_events}),
                "dependency_kinds": sorted({dependency.kind for dependency in self.dependencies}),
                "dependency_count": len(self.dependencies),
                "intervention_slot": self.intervention.slot_id,
                "assertion_predicates": sorted({item.predicate for item in self.design_assertions}),
                "payload_factors": {key: value for key, value in sorted(self.suite_payload.items())
                                    if self.field_provenance.get(f"suite_payload.{key}") != "SURFACE_ONLY"}}

    def digest(self) -> str:
        return canonical_sha256(self.as_dict())


def blueprint_from_ir(ir: MechanismIR, business_binding: Any = None, *,
                      difficulty: str = "M") -> dict[str, Any]:
    """Project a VALIDATED IR onto the suite payload its compiler consumes.

    Fail-closed (R2-G2): every ``ir.validate()`` error blocks projection — zero
    agents, dependency cycles, unknown endpoints and dangling evidence never
    reach the compiler. When a typed ``BusinessBinding`` is supplied it must be
    internally consistent, consistent with the IR, and the suite compiler must
    accept it; the binding is program-owned and injected here, never model-set.
    """
    errors = ir.validate()
    if errors:
        raise ValueError("CAPABILITY_GAP: invalid IR " + "; ".join(errors))
    if business_binding is not None:
        integrity = business_binding.validate_integrity()
        if integrity:
            raise ValueError("CAPABILITY_GAP: invalid business binding " + "; ".join(integrity))
        consistency = business_binding.consistency_with_ir(ir)
        if consistency:
            raise ValueError("CAPABILITY_GAP: binding inconsistent with IR " + "; ".join(consistency))
        if any(key == "business_binding" for key in ir.suite_payload):
            raise ValueError("CAPABILITY_GAP: business binding must be program-injected, not IR-payload data")
    from ioabench.v5.ai_generation.pipeline import suite_spec
    spec = suite_spec(ir.suite, typed=True)
    constraints = spec.adapter.generator_constraints(
        subtype=_subtype(ir.suite, difficulty), difficulty=difficulty)
    schema = constraints.get("schema") or constraints.get("schema")
    payload_schema = schema.get("properties", {}).get("suite_payload", {})
    allowed = set(payload_schema.get("properties", {}))
    unknown = sorted(set(ir.suite_payload) - allowed - {"business_binding"})
    if unknown:
        raise ValueError("CAPABILITY_GAP: factors outside the compiler grammar: " + str(unknown))
    if business_binding is not None and "business_binding" not in allowed:
        raise ValueError("CAPABILITY_GAP: suite compiler does not consume business bindings")
    example = constraints.get("example_blueprint", constraints.get("example"))
    blueprint = dict(example)
    blueprint["difficulty"] = difficulty
    # merge onto the NON-grammar example extras only (same rule as assemble_blueprint):
    # enriched example values for schema keys must never leak into a projection
    example_payload = dict(example.get("suite_payload", {}))
    non_grammar = {key: value for key, value in example_payload.items()
                   if key not in allowed}
    blueprint["suite_payload"] = {**non_grammar, **dict(ir.suite_payload)}
    if ir.suite.split("-")[0] == "T321" and "offer_profiles" not in blueprint["suite_payload"]:
        # program-owned default, same rule as assemble_blueprint (never model-set)
        from ioabench.v5.ai_generation.t321_dyna_compiler import _offer_profiles
        blueprint["suite_payload"]["offer_profiles"] = _offer_profiles(
            int(blueprint["suite_payload"].get("broker_count", 2)))
    if business_binding is not None:
        blueprint["suite_payload"]["business_binding"] = business_binding.as_dict()
    findings = list(spec.adapter.validate_blueprint(blueprint))
    if findings:
        raise ValueError("CAPABILITY_GAP: compiled projection rejected: " + str(findings))
    return blueprint


def _subtype(suite: str, difficulty: str = "M") -> str:
    canonical = suite.split("-")[0]
    # T362's H-difficulty base pairs live in other subtypes (S1 is E/M only)
    if canonical == "T362" and difficulty == "H":
        return "T362-S2"
    return {"T313": "T313-S4", "T311": "T311-S2", "T312": "T312-S2", "T322": "T322-S1", "T323": "T323-S1", "T331": "T331-S5", "T321": "T321-S5", "T343": "T343-S1", "T351": "T351-S1", "T352": "T352-S1", "T353": "T353-S1", "T362": "T362-S1"}.get(canonical, "T331-S5")


def ir_from_blueprint(suite: str, blueprint: Mapping[str, Any], *,
                      business_branch: str = "unspecified") -> MechanismIR:
    """Compatibility adapter: lift an existing compiler-consumed blueprint into an IR.

    The blueprint is never modified and its canonical hash is unaffected; structural
    payload fields are MODEL_PROPOSED factors that the compiler consumed, while truth,
    pairing and scoring remain PROGRAM_TRUTH.
    """
    from ioabench.v5.ai_generation.pipeline import suite_spec
    canonical = suite.split("-")[0]
    spec = suite_spec(suite, typed=True)
    payload = dict(blueprint.get("suite_payload", {}))
    compiled = spec.adapter.compile_pair(dict(blueprint), seed=0)
    control, risk = compiled
    slots = list(control.mechanism_slots)
    agents = tuple(IRAgent(agent.agent_id, agent.role, tuple(agent.tools))
                   for agent in spec.scenario_factory().agents(control.world))
    assets = tuple(IRAsset(name, "world_key", "compiler") for name in sorted(control.world))
    evidence = tuple(IREvidence(slot.strip("/").replace("/", "_"), "mechanism_slot",
                                tuple(agent.id for agent in agents))
                     for slot in slots)
    intervention = IRIntervention(slots[0] if slots else "unknown",
                                  str(_slot_value(control.world, slots[0] if slots else "")),
                                  str(_slot_value(risk.world, slots[0] if slots else "")))
    provenance = {f"suite_payload.{key}": "MODEL_PROPOSED" for key in payload}
    provenance.update({"intervention": "PROGRAM_TRUTH", "oracle": "PROGRAM_TRUTH",
                       "scorer": "PROGRAM_TRUTH", "business_branch": "SURFACE_ONLY"})
    return MechanismIR(MECHANISM_IR_VERSION, suite, business_branch, agents, assets, evidence,
                       (), (), intervention, canonical,
                       tuple(slots), (), surface={}, suite_payload=payload,
                       field_provenance=provenance)


def _slot_value(world: Mapping[str, Any], pointer: str) -> Any:
    if not pointer:
        return None
    value: Any = world
    for token in pointer.strip("/").split("/"):
        if not isinstance(value, Mapping) or token not in value:
            return None
        value = value[token]
    return value
