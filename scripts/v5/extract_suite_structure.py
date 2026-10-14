"""M1 extractor: objective structural facts of the 18 v5 suites.

For every suite module this scans, with zero provider calls:
  * module identity (scenario/scorer/generator versions);
  * agents (ids, roles, tool sets) as declared by ``Scenario.agents`` on a sampled world;
  * tools (name, decision flag, parameter schema keys);
  * initial-state keys;
  * world keys and mechanism slots / fingerprints / oracle keys from sampled CONTROL and RISK
    cases (``generate`` with small family counts);
  * the construct-map fields that drive the dynamic-world capability mapping (subtypes,
    manipulation, exposure definition, norms, utility, recovery).

Output: artifacts/v5/dynamic_world/suite-structure-scan.json (new file; refuses overwrite).

This is a read-only evidence scan for the M1 capability contract — it changes nothing.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.core.case import Case  # noqa: E402
from ioabench.v5.suites import SUITE_MODULES, load  # noqa: E402

DEST = ROOT / "artifacts/v5/dynamic_world/suite-structure-scan.json"
CONSTRUCT_MAP = ROOT / "contracts/v5/construct_maps.json"
SAMPLE_SEED = 5
SAMPLE_FAMILIES = 3

# construct-map fields copied verbatim into the scan (they are the scientific authority for M1)
CM_FIELDS = ("name_zh", "name_en", "classification", "canonical_question", "intended_construct",
             "out_of_construct", "mechanism_subtypes", "causal_hypothesis", "manipulation",
             "exposure_definition", "action_opportunity", "norms", "safe_behaviors", "unsafe_behavior",
             "task_utility", "over_restriction", "recovery", "consequence_persisted",
             "verification_metric", "difficulty", "exclusions", "confounders")


def case_facts(case: Case) -> dict[str, object]:
    return {
        "arm": case.arm,
        "subtype": case.subtype,
        "difficulty": case.difficulty,
        "domain": case.domain,
        "world_keys": sorted(case.world),
        "mechanism_slots": list(case.mechanism_slots),
        "fingerprints": list(case.fingerprints),
        "oracle_keys": sorted(case.oracle),
    }


def main() -> int:
    if DEST.exists():
        print(f"REFUSED: {DEST} already exists", file=sys.stderr)
        return 1
    construct = json.loads(CONSTRUCT_MAP.read_text(encoding="utf-8"))
    suites: dict[str, object] = {}
    for suite_id in SUITE_MODULES:
        module = load(suite_id)
        scenario = getattr(module, f"{suite_id}Scenario")()
        pairs = module.generate(SAMPLE_SEED, families=SAMPLE_FAMILIES)
        control, risk = pairs[0]
        world = control.world
        agents = [
            {"agent_id": a.agent_id, "organization": a.organization, "role": a.role,
             "tools": list(a.tools), "system_prompt_chars": len(a.system_prompt)}
            for a in scenario.agents(world)
        ]
        tools = {}
        for name, spec in scenario.tools(world).items():
            tools[name] = {"decision": spec.decision,
                           "parameters_required": list(spec.parameters.get("required", [])),
                           "parameters_properties": sorted(spec.parameters.get("properties", {}))}
        state_keys = sorted(scenario.initial_state(world))
        cm = construct["suites"][suite_id]
        cm_subset = {field: cm.get(field) for field in CM_FIELDS}
        # scripted reference policies and their expected labels
        expected = getattr(module, "EXPECTED_REFERENCE", {})
        policies = sorted(module.policies()) if hasattr(module, "policies") else []
        suites[suite_id] = {
            "scenario_version": module.SCENARIO_VERSION,
            "scorer_version": module.SCORER_VERSION,
            "generator_version": module.GENERATOR_VERSION,
            "simulation_only": suite_id in ("T361", "T362", "T363"),
            "agents": agents,
            "tools": tools,
            "decision_tools": sorted(n for n, s in scenario.tools(world).items() if s.decision),
            "initial_state_keys": state_keys,
            "sample_cases": {"control": case_facts(control), "risk": case_facts(risk)},
            "sample_subtypes": sorted({c.subtype for pair in pairs for c in pair}),
            "sample_difficulties": sorted({c.difficulty for pair in pairs for c in pair}),
            "reference_policies": policies,
            "expected_reference": {k: dict(v) for k, v in expected.items()},
            "construct_map": cm_subset,
        }
    result = {
        "kind": "ioabench.v5.dynamic-world.suite-structure-scan/1",
        "note": ("read-only M1 evidence: objective structure of the 18 suite modules as implemented, "
                 "plus verbatim construct-map fields; no construct is redefined by this scan"),
        "sample_seed": SAMPLE_SEED,
        "sample_families": SAMPLE_FAMILIES,
        "suites": suites,
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK suites={len(suites)} -> {DEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
