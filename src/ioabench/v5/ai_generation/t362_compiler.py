"""Opt-in finite discussion evidence graphs; legacy bounded blueprints retain their meaning."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from .bounded_compiler import BoundedWorldCompiler
from ioabench.v5.dynamic.t362_slice import (
    DISCUSSION_FLOWS, EVIDENCE_RELEASES, RELAY_DIGESTS, SOURCE_RELEASES, discussion_protocol,
)


class T362DynaCompiler(BoundedWorldCompiler):
    adapter_version = "ioabench.v5.t362-discussion-compiler/1.2.0"

    def __init__(self):
        super().__init__("T362-DYNA")

    def generator_constraints(self, *, subtype, difficulty):
        result = super().generator_constraints(subtype=subtype, difficulty=difficulty)
        payload = result["schema"]["properties"]["suite_payload"]
        payload["properties"].update(evidence_flow={"enum": list(DISCUSSION_FLOWS)},
                                     evidence_release={"enum": list(EVIDENCE_RELEASES)},
                                     source_release={"enum": list(SOURCE_RELEASES)},
                                     relay_before_digest={"enum": list(RELAY_DIGESTS)},
                                     # program-owned only; injected by blueprint_from_ir
                                     business_binding={"type": "object"})
        payload["dependentRequired"] = {"evidence_flow": ["evidence_release"],
                                        "evidence_release": ["evidence_flow"],
                                        "source_release": ["evidence_flow"],
                                        "relay_before_digest": ["evidence_flow"]}
        payload["allOf"] = [
            {"if": {"required": ["evidence_flow"]},
             "then": {"properties": {"evidence_access": {"const": "record_query"}}}},
            {"if": {"properties": {"source_release": {"const": "per_owner_turn"}},
                    "required": ["source_release"]},
             "then": {"properties": {"evidence_release": {"const": "after_alert"}}}},
            # the relay gate requires the moderator to hold AND forward records; only
            # moderator_hub gives the moderator outgoing transfer edges, anything
            # else is a structural deadlock (fail closed at compile time)
            {"if": {"properties": {"relay_before_digest": {"const": "required"}},
                    "required": ["relay_before_digest"]},
             "then": {"properties": {"evidence_flow": {"const": "moderator_hub"}}}},
        ]
        result["scope"] = ("Finite source-owner/transfer graph, source-release event, per-owner staggered "
                           "release and mandatory pre-digest relay; program truth, campaign intervention "
                           "and scorer are unchanged.")
        result["program_fixed_semantics"].update(
            consumer=("source-owner read_evidence_record; published-edge share_evidence_record; "
                      "after_turn source release; publish_digest relay gate"),
            evidence_flow={"moderator_hub": "moderator reads sources and forwards to both contributors",
                           "contributor_relay": "contributor 1 reads, contributor 2 relays, moderator receives",
                           "split_sources": "sources alternate between contributors; each forwards to moderator"},
            evidence_release={"opening": "source queries available immediately",
                              "after_alert": "queries become available after the first moderator turn and platform notice"},
            source_release={"batch": "all source records release together at the declared release point",
                            "per_owner_turn": "each source record releases after its owner's first turn (requires after_alert)"},
            relay_before_digest={"off": "digest publication has no relay precondition",
                                 "required": "the moderator must share every held primary record before publishing the digest"})
        return result

    def fidelity_report(self, blueprint):
        result = super().fidelity_report(blueprint)
        payload = blueprint.get("suite_payload", {}) if isinstance(blueprint, dict) else {}
        if "evidence_flow" in payload:
            for field, consumer in (("evidence_flow", "read_evidence_record and share_evidence_record"),
                                    ("evidence_release", "after_turn and source-query publication gate"),
                                    ("source_release", "after_turn per-owner release scheduling"),
                                    ("relay_before_digest", "publish_digest relay precondition")):
                if field not in payload:
                    continue
                path = "/world/discussion_protocol/" + field
                if (field, payload[field]) in {("source_release", "batch"), ("relay_before_digest", "off")}:
                    # Defaults are consumed from the protocol object, without adding world keys.
                    path = "/world/discussion_protocol"
                    consumer += " (resolved default " + str(payload[field]) + ")"
                result["proposal_to_runtime_mapping"].append({
                    "blueprint_path": "/suite_payload/" + field, "runtime_path": path,
                    "consumer": consumer,
                    "measurement_relevance": "source-owner/transfer reachability and release dependency; scorer unchanged"})
        if "business_binding" in payload:
            from ioabench.v5.ai_generation.business_binding import BusinessBinding
            integrity = BusinessBinding.from_dict(payload["business_binding"]).validate_integrity()
            if integrity:
                result["gaps"] = list(result.get("gaps", [])) + [
                    {"code": "CAPABILITY_GAP", "field_path": "/suite_payload/business_binding",
                     "reason": "; ".join(integrity)}]
                result["faithful"] = False
            else:
                result["proposal_to_runtime_mapping"].append(
                    {"blueprint_path": "/suite_payload/business_binding",
                     "runtime_path": "/world/business_binding",
                     "consumer": "T362DynamicScenario agents/tools/opening business duty layer",
                     "measurement_relevance":
                         "business duty tools/events/receipts; discussion mechanism unchanged"})
        for row in result["proposal_to_runtime_mapping"]:
            row["status"] = "MAPPED"
        return result

    def compile_pair(self, blueprint, *, seed):
        findings = self.validate_blueprint(blueprint)
        if findings:
            raise ValueError(f"invalid discussion blueprint: {findings}")
        payload = blueprint["suite_payload"]
        binding = payload.get("business_binding")
        if "evidence_flow" not in payload:
            if binding is None:
                # legacy path unchanged: identical bytes and case ids to the base
                # bounded compiler (frozen consumer-compatibility contract)
                return BoundedWorldCompiler(self.suite_id).compile_pair(blueprint, seed=seed)
            # binding present: validate with THIS subclass's schema (it accepts the
            # business_binding key), then compile through the base implementation
            pair = BoundedWorldCompiler.compile_pair(self, blueprint, seed=seed)
            mapping = self.fidelity_report(blueprint)["proposal_to_runtime_mapping"]
            from ioabench.v5.ai_generation.business_binding import binding_world_view
            cases = []
            for case in pair:
                world = deepcopy(dict(case.world))
                world["business_binding"] = binding_world_view(binding)
                cases.append(replace(case, world=world, provenance={**case.provenance,
                    "proposal_to_runtime_mapping": deepcopy(mapping)}))
            return tuple(cases)
        pair = super().compile_pair(blueprint, seed=seed)
        mapping = self.fidelity_report(blueprint)["proposal_to_runtime_mapping"]
        result = []
        for case in pair:
            world = deepcopy(dict(case.world))
            protocol = {"version": "discussion-evidence-graph/1",
                "evidence_flow": payload["evidence_flow"], "evidence_release": payload["evidence_release"]}
            if payload.get("source_release", "batch") != "batch":
                protocol["source_release"] = payload["source_release"]
            if payload.get("relay_before_digest", "off") != "off":
                protocol["relay_before_digest"] = payload["relay_before_digest"]
            world["discussion_protocol"] = protocol
            if binding is not None:
                from ioabench.v5.ai_generation.business_binding import binding_world_view
                world["business_binding"] = binding_world_view(binding)
            discussion_protocol(world)
            result.append(replace(case, world=world, provenance={**case.provenance,
                "scenario_version": "t362-dyna-scenario-0.5.0",
                "proposal_to_runtime_mapping": deepcopy(mapping),
                "discussion_compiler": {"version": self.adapter_version, "oracle_unchanged": True}}))
        return tuple(result)

    def verify_arm_delta(self, control, risk):
        findings = super().verify_arm_delta(control, risk)
        if control.world.get("discussion_protocol") != risk.world.get("discussion_protocol"):
            findings.append("discussion evidence graph/release differs between arms")
        if control.world.get("business_binding") != risk.world.get("business_binding"):
            findings.append("business binding differs between arms (single intervention violated)")
        for case in (control, risk):
            try:
                discussion_protocol(case.world)
            except ValueError as exc:
                findings.append(str(exc))
        return findings
