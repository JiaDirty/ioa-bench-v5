"""Bounded narrative enrichment of the existing program-grounded dynamic suites.

This adapter changes public prose only; it does not author a new executable structure.
The original text is retained verbatim and every addition still needs independent
semantic review before a candidate can be accepted or frozen.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import re
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256
from ioabench.v5.core.case import Case, DIFFICULTIES, resolve_pointer, validate_case
from ioabench.v5.dynamic.registry import get_adapter, implemented
from ioabench.v5.dynamic.signature import executable_structure_signature


ADAPTER_VERSION = "v5-runtime-narrative-enrichment/1.0.0"
# Each field is actually rendered by the registered scenario; policies, numeric
# facts, evidence contents, authorities, tool ids and mechanism slots stay fixed.
NARRATIVE_PATHS = {
    "T311-DYNA": ("/engagement/title",),
    "T312-DYNA": ("/brief",),
    "T313-DYNA": ("/downstream_request/body",),
    "T321-DYNA": ("/business_context/record_type",),
    "T321-DYNB": ("/business_context/record_type",),
    "T322-DYNA": ("/instruction/description",),
    "T323-DYNA": ("/work_order/subject",),
    "T331-DYNA": ("/brief",),
    "T332-DYNA": ("/records/0/note",),
    "T333-DYNA": ("/brief",),
    "T341-DYNA": ("/packets/0/packet/note",),
    "T342-DYNA": ("/claim/headline",),
    "T343-DYNA": ("/requests/0/subject",),
    "T351-DYNA": ("/brief",),
    "T352-DYNA": ("/providers/PRV-CHG",),
    "T353-DYNA": ("/brief",),
    "T361-DYNA": ("/channel_header",),
    "T362-DYNA": ("/posts/2/headline",),
    "T363-DYNA": ("/tasks/0/source_record_type",),
}
_UNSUPPORTED = re.compile(
    r"https?://|www\.|\b(?:public internet|external network|internet access|"
    r"must|shall|required|mandatory|new requirement|only if|override|bypass|"
    r"benchmark|oracle|ground truth|scoring rule|attack label|safe answer)\b|"
    r"\b[a-z][a-z0-9]*_[a-z][a-z0-9_]*\b|```|"
    r"\b(?:import|exec|eval)\s*\(|<script|"
    r"必须|强制|新增要求|公网|评分规则|标准答案|绕过",
    re.IGNORECASE,
)


def _finding(code: str, path: str, detail: str) -> dict[str, str]:
    return {"code": code, "path": path, "detail": detail}


def _set_pointer(world: Any, pointer: str, value: str) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    parent = world
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    if isinstance(parent, list):
        parent[int(parts[-1])] = value
    else:
        parent[parts[-1]] = value


class RuntimeGenerationAdapter:
    """GeneratedSuiteAdapter for the current versioned public-text boundary."""

    adapter_version = ADAPTER_VERSION

    def __init__(self, suite_id: str) -> None:
        if suite_id not in NARRATIVE_PATHS:
            raise ValueError(f"unsupported narrative suite {suite_id}")
        self.suite_id = suite_id
        self.slice_module = get_adapter(suite_id)

    def _base_pair(self, *, seed: int, subtype: str, difficulty: str) -> tuple[Case, Case]:
        pairs = self.slice_module.generate(seed, families=3)
        pair = next((pair for pair in pairs if pair[0].subtype == subtype
                     and pair[0].difficulty == difficulty), None)
        if pair is None:
            raise ValueError(f"unsupported {self.suite_id} subtype/difficulty: {subtype}/{difficulty}")
        return pair

    def generator_context(self, *, seed: int, difficulty: str | None = None) -> dict[str, Any]:
        """Exact input plus constraints; an explicit unavailable difficulty is a gap."""
        pairs = self.slice_module.generate(seed, families=3)
        available = sorted({pair[0].difficulty for pair in pairs})
        selected = difficulty or ("M" if "M" in available else available[0])
        pair = next((pair for pair in pairs if pair[0].difficulty == selected), None)
        if pair is None:
            raise ValueError(f"{self.suite_id}: existing template has difficulties {available}, not {selected}")
        context = self.candidate_context(seed=seed, subtype=pair[0].subtype, difficulty=selected)
        constraints = dict(self.generator_constraints(subtype=pair[0].subtype, difficulty=selected))
        constraints["public_example_context"] = context
        path = NARRATIVE_PATHS[self.suite_id][0]
        constraints["example"]["world_edits"][0]["value"] = context["public_text_fields"][path] \
            + " Context: this is a routine local workflow."
        return {**context, "constraints": constraints,
                "available_difficulties": available}

    def default_blueprint(self, *, seed: int, difficulty: str | None = None) -> dict[str, Any]:
        context = self.generator_context(seed=seed, difficulty=difficulty)
        path = NARRATIVE_PATHS[self.suite_id][0]
        return {"suite_id": self.suite_id, "subtype": context["subtype"],
                "difficulty": context["difficulty"], "world_edits": [{"path": path,
                    "value": context["public_text_fields"][path]
                             + " Context: this is a routine local workflow."}]}

    def candidate_context(self, *, seed: int, subtype: str, difficulty: str) -> dict[str, Any]:
        """Seed-specific public input for the generator; no arm or Oracle fields."""
        control, risk = self._base_pair(seed=seed, subtype=subtype, difficulty=difficulty)
        texts = {}
        for path in NARRATIVE_PATHS[self.suite_id]:
            original = resolve_pointer(control.world, path)
            if original != resolve_pointer(risk.world, path) or not isinstance(original, str):
                raise ValueError(f"enrichment boundary drift: {path} is not a shared string")
            if any(path == slot or path.startswith(slot + "/") for slot in control.mechanism_slots):
                raise ValueError(f"enrichment boundary overlaps mechanism: {path}")
            texts[path] = original
        return {"suite_id": self.suite_id, "subtype": subtype, "difficulty": difficulty,
                "seed": seed, "public_text_fields": texts,
                "scope": "Append neutral context; keep each original string verbatim as the prefix."}

    def generator_constraints(self, *, subtype: str, difficulty: str) -> Mapping[str, Any]:
        context = self.candidate_context(seed=0, subtype=subtype, difficulty=difficulty)
        paths = list(NARRATIVE_PATHS[self.suite_id])
        schema = {"type": "object", "additionalProperties": False,
                  "required": ["suite_id", "subtype", "difficulty", "world_edits"],
                  "properties": {
                      "suite_id": {"const": self.suite_id}, "subtype": {"const": subtype},
                      "difficulty": {"const": difficulty},
                      "world_edits": {"type": "array", "minItems": 1, "maxItems": len(paths),
                          "items": {"type": "object", "additionalProperties": False,
                                    "required": ["path", "value"], "properties": {
                                        "path": {"enum": paths},
                                        "value": {"type": "string", "minLength": 1, "maxLength": 1600}}}}}}
        return {"adapter_version": self.adapter_version, "schema": schema,
                "allowed_paths": paths, "public_example_context": context,
                "seed_context_method": "candidate_context(seed, subtype, difficulty)",
                "max_added_characters": 240, "diversity_kind": "NARRATIVE_VARIANT",
                "semantic_review_required": True,
                "scope": "Existing supported template only; no new topology, tools, truth, authority, "
                         "requirements or task. Lexical checks are mechanical, not semantic proof.",
                "example": {"suite_id": self.suite_id, "subtype": subtype, "difficulty": difficulty,
                            "world_edits": [{"path": paths[0],
                                "value": context["public_text_fields"][paths[0]]
                                         + " Context: this is a routine local workflow."}]}}

    def validate_blueprint(self, blueprint: Mapping[str, Any]) -> list[dict[str, str]]:
        if not isinstance(blueprint, Mapping):
            return [_finding("SCHEMA", "", "payload must be an object")]
        findings = []
        expected_keys = {"suite_id", "subtype", "difficulty", "world_edits"}
        if set(blueprint) != expected_keys:
            findings.append(_finding("SCHEMA", "", "payload keys must be exactly the declared four keys"))
        if blueprint.get("suite_id") != self.suite_id:
            findings.append(_finding("IDENTITY", "/suite_id", "suite identity does not match adapter"))
        subtype, difficulty = blueprint.get("subtype"), blueprint.get("difficulty")
        try:
            self._base_pair(seed=0, subtype=subtype, difficulty=difficulty)
        except (ValueError, TypeError):
            findings.append(_finding("CAPABILITY_GAP", "/subtype", "unsupported subtype/difficulty"))
        if difficulty not in DIFFICULTIES:
            findings.append(_finding("SCHEMA", "/difficulty", "difficulty must be an existing E/M/H label"))
        edits = blueprint.get("world_edits")
        if not isinstance(edits, list) or not 1 <= len(edits) <= len(NARRATIVE_PATHS[self.suite_id]):
            return [*findings, _finding("SCHEMA", "/world_edits", "edits must be a nonempty bounded list")]
        seen = set()
        for index, edit in enumerate(edits):
            pointer = f"/world_edits/{index}"
            if not isinstance(edit, Mapping) or set(edit) != {"path", "value"}:
                findings.append(_finding("SCHEMA", pointer, "edit keys must be exactly path and value"))
                continue
            path, value = edit["path"], edit["value"]
            if not isinstance(path, str) or path not in NARRATIVE_PATHS[self.suite_id]:
                findings.append(_finding("CAPABILITY_GAP", pointer + "/path", "unknown or protected world path"))
            elif path in seen:
                findings.append(_finding("SCHEMA", pointer + "/path", "duplicate edit path"))
            else:
                seen.add(path)
            if not isinstance(value, str) or not value.strip() or len(value) > 1600:
                findings.append(_finding("SCHEMA", pointer + "/value", "value must be a bounded nonempty string"))
        return findings

    def fidelity_report(self, blueprint: Mapping[str, Any]) -> Mapping[str, Any]:
        gaps = self.validate_blueprint(blueprint)
        edits = blueprint.get("world_edits", []) if isinstance(blueprint, Mapping) else []
        mappings = [{"blueprint_path": f"/world_edits/{i}/value", "runtime_path": "/world" + edit["path"],
                     "operation": "SHARED_ADDITIVE_PUBLIC_TEXT"}
                    for i, edit in enumerate(edits) if isinstance(edit, Mapping)
                    and edit.get("path") in NARRATIVE_PATHS[self.suite_id]] if isinstance(edits, list) else []
        return {"version": self.adapter_version, "faithful": not gaps, "gaps": gaps,
                "proposal_to_runtime_mapping": mappings, "semantic_review_required": True,
                "semantic_status": "NOT_REVIEWED", "diversity_kind": "NARRATIVE_VARIANT"}

    def compile_pair(self, blueprint: Mapping[str, Any], *, seed: int) -> tuple[Case, Case]:
        findings = self.validate_blueprint(blueprint)
        if findings:
            raise ValueError(f"invalid narrative blueprint: {findings}")
        base = self._base_pair(seed=seed, subtype=blueprint["subtype"], difficulty=blueprint["difficulty"])
        context = self.candidate_context(seed=seed, subtype=blueprint["subtype"], difficulty=blueprint["difficulty"])
        originals = []
        for index, edit in enumerate(blueprint["world_edits"]):
            original, value = context["public_text_fields"][edit["path"]], edit["value"]
            if not value.startswith(original) or not value[len(original):].strip():
                raise ValueError(f"world_edits/{index}: original text must be preserved and context added")
            suffix = value[len(original):]
            if len(suffix) > 240 or _UNSUPPORTED.search(suffix):
                raise ValueError(f"world_edits/{index}: unsupported requirement, tool, code, network or leakage text")
            if any(ord(char) < 32 and char not in "\n\t" for char in suffix):
                raise ValueError(f"world_edits/{index}: unsupported control character")
            originals.append({"path": edit["path"], "original_value": original})
        digest = canonical_sha256({"version": self.adapter_version, "blueprint": blueprint, "seed": seed})
        pair_id = f"{base[0].pair_id}-text-{digest[:12]}"
        cases = []
        for case in base:
            world = deepcopy(dict(case.world))
            for edit in blueprint["world_edits"]:
                _set_pointer(world, edit["path"], edit["value"])
            compiled = replace(case, case_id=f"{case.case_id}-text-{digest[:12]}", pair_id=pair_id,
                               world=world, oracle=deepcopy(dict(case.oracle)), provenance={
                                   **deepcopy(dict(case.provenance)), "narrative_enrichment": {
                                       "adapter_version": self.adapter_version, "input_sha256": digest,
                                       "seed": seed, "source_pair_id": case.pair_id,
                                       "diversity_kind": "NARRATIVE_VARIANT", "semantic_review_required": True,
                                       "semantic_status": "NOT_REVIEWED", "original_fields": deepcopy(originals)}})
            validate_case(compiled, allow_dynamic=True)
            cases.append(compiled)
        return cases[0], cases[1]

    def verify_arm_delta(self, control: Case, risk: Case) -> list[str]:
        return self.slice_module.fine_arm_delta(control, risk)

    def structural_signature(self, case: Case) -> Mapping[str, Any]:
        # Restore enrichment only: wording cannot create a structural family.
        raw = deepcopy(case.as_dict())
        for edit in case.provenance.get("narrative_enrichment", {}).get("original_fields", []):
            _set_pointer(raw["world"], edit["path"], edit["original_value"])
        return executable_structure_signature(raw)


def runtime_narrative_adapters() -> dict[str, RuntimeGenerationAdapter]:
    if set(implemented()) != set(NARRATIVE_PATHS):
        raise ValueError("dynamic registry changed; audit narrative field boundaries before enabling new slices")
    return {suite_id: RuntimeGenerationAdapter(suite_id) for suite_id in implemented()}
