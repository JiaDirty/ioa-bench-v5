"""M1 validator: consistency of the dynamic-world capability contract.

Checks (zero provider calls):
  1. the contract file exists, parses, and declares the current schema version;
  2. its suite set equals the 18 registered suite ids, and each suite's subtype ids equal the
     construct map's mechanism_subtypes ids (no construct is redefined);
  3. every suite's shared capabilities are registered components whose required_by includes
     that suite, and event_ledger is required everywhere;
  4. every suite's declared evaluation facts name at least one decision tool that exists in
     the live suite module (re-derived from source, not trusted from the scan);
  5. oracle facts referenced by state predicates exist among the suite's oracle keys
     (sampled case, seed 5);
  6. each suite declares at least one dynamic extension and at least one current-engine gap.

Exit code 0 = consistent. Used by tests/v5/test_capability_maps.py; CLI for CI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.suites import SUITE_MODULES, load  # noqa: E402

CONTRACT = ROOT / "contracts/v5/dynamic_world_capability_maps.json"
CONSTRUCT_MAP = ROOT / "contracts/v5/construct_maps.json"
SCAN = ROOT / "artifacts/v5/dynamic_world/suite-structure-scan.json"
SCHEMA_VERSION = "ioabench.v5.dynamic-world.capability-maps/1"


def validate() -> list[str]:
    failures: list[str] = []
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    construct = json.loads(CONSTRUCT_MAP.read_text(encoding="utf-8"))
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    if contract.get("schema_version") != SCHEMA_VERSION:
        failures.append(f"schema_version {contract.get('schema_version')!r} != {SCHEMA_VERSION!r}")
    if contract.get("status") not in ("DRAFT", "FROZEN"):
        failures.append(f"illegal status {contract.get('status')!r}")
    components = contract.get("shared_components", {})
    suites = contract.get("suites", {})
    if set(suites) != set(SUITE_MODULES):
        failures.append(f"suite set mismatch: contract={sorted(suites)} vs registry={sorted(SUITE_MODULES)}")
    for suite_id, entry in suites.items():
        cm = construct["suites"][suite_id]
        want_subtypes = [st["id"] for st in cm["mechanism_subtypes"]]
        got_subtypes = [st["id"] for st in entry.get("subtypes", [])]
        if got_subtypes != want_subtypes:
            failures.append(f"{suite_id}: subtype ids {got_subtypes} != construct map {want_subtypes}")
        shared = entry.get("capabilities", {}).get("shared", [])
        for component in shared:
            if component not in components:
                failures.append(f"{suite_id}: unregistered component {component}")
            elif suite_id not in components[component]["required_by"]:
                failures.append(f"{suite_id}: component {component} does not list the suite in required_by")
        if "event_ledger" not in shared:
            failures.append(f"{suite_id}: event_ledger is mandatory")
        # decision tools referenced by evaluation facts must exist in the live module
        module = load(suite_id)
        pairs = module.generate(seed=5, families=1)
        control = pairs[0][0]
        scenario = getattr(module, f"{suite_id}Scenario")()
        live_tools = set(scenario.tools(control.world))
        decision_live = {name for name in live_tools if scenario.tools(control.world)[name].decision}
        facts = entry.get("evaluation_facts", {})
        named_events = [e for e in facts.get("events", []) if isinstance(e, str)]
        if not named_events:
            failures.append(f"{suite_id}: evaluation_facts.events empty")
        # oracle facts must be a subset of the sampled oracle keys
        oracle_keys = set(scan["suites"][suite_id]["sample_cases"]["control"]["oracle_keys"])
        missing_oracle = [f for f in facts.get("oracle_facts", []) if f not in oracle_keys]
        if missing_oracle:
            failures.append(f"{suite_id}: oracle_facts not in sampled oracle: {missing_oracle}")
        if not entry.get("dynamic_extensions"):
            failures.append(f"{suite_id}: dynamic_extensions empty")
        if not entry.get("capability_gaps_current_engine"):
            failures.append(f"{suite_id}: capability_gaps_current_engine empty")
        # at least one declared event mentions a live decision tool token
        joined = " ".join(named_events)
        if not any(tool in joined for tool in decision_live):
            failures.append(f"{suite_id}: no evaluation event references a live decision tool {sorted(decision_live)}")
    return failures


def main() -> int:
    failures = validate()
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print(f"OK {CONTRACT.relative_to(ROOT).as_posix()} consistent with construct maps and live suite modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
