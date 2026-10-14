"""Gate C data-quality and diversity audit for v5 datasets.

Usage: python scripts/v5/data_quality.py --version 5.1.0 [--suites T311 T351 ...]

Per suite it computes from data/v5/datasets/<suite>/<version>/cases.jsonl:
- coverage: pairs, families, subtype x difficulty, domains;
- entity-normalized visible text (domain-kit names, ids, numbers, dates replaced by placeholders);
- entity_substitution_only: RISK cases whose normalized world equals that of a case from another family;
- cross-family near duplicates: token-set Jaccard >= 0.90 between normalized RISK worlds of different families;
- effective_family_n: connected components of families under the near-duplicate relation;
- structural diversity: distinct witness tool paths per subtype;
- pair-diff and static firewall re-check.
Writes artifacts/v5/data_quality/<version>/report.json and prints a summary table.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.core.case import case_from_dict, pair_diff_violations  # noqa: E402
from ioabench.v5.core.engine import run_episode  # noqa: E402
from ioabench.v5.core.firewall import ObservationFirewall  # noqa: E402
from ioabench.v5.gates import PROFILE, check_pair  # noqa: E402
from ioabench.v5.suites import load  # noqa: E402
from ioabench.v5.worlds import DOMAINS  # noqa: E402

NEAR_DUP = 0.90
_ENTITIES = sorted({name for d in DOMAINS for pool in (d.orgs, d.people, d.counterparties) for name in pool},
                   key=len, reverse=True)
_ENTITY_RE = re.compile("|".join(re.escape(e) for e in _ENTITIES), re.IGNORECASE)
_ID_RE = re.compile(r"\b(?:[A-Z]{2,5}-[A-Z0-9-]*\d[A-Z0-9-]*|[A-Z]{1,8}\d{2,}[A-Z0-9-]*)\b",
                    re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUM_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_TOKEN_RE = re.compile(r"[a-z0-9<>_]+")


def normalize(text: str) -> str:
    text = _ENTITY_RE.sub("<ENT>", text)
    text = _DATE_RE.sub("<DATE>", text)
    text = _ID_RE.sub("<ID>", text)
    return _NUM_RE.sub("<NUM>", text).lower()


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


async def _tool_path(case: Any, module: Any, policy_name: str) -> dict[str, Any]:
    auxiliary = module.reference_auxiliary() if hasattr(module, "reference_auxiliary") else None
    trace = await run_episode(case, getattr(module, f"{case.suite_id}Scenario")(), module.policies()[policy_name],
                              PROFILE, parameters={}, auxiliary=auxiliary)
    firewall = ObservationFirewall()
    findings = []
    visible_shapes = set()
    for index, record in enumerate(trace.records):
        request = record.get("request", {})
        matches = firewall.scan(request)
        findings.extend({"record": index, "kind": f.kind, "path": f.path, "match": f.match} for f in matches)
        for message in request.get("messages", []):
            content = message.get("content", "")
            if not isinstance(content, str):
                continue
            start = content.find("{")
            if start < 0:
                continue
            try:
                payload = json.loads(content[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                visible_shapes.add(_canonical({k: _shape(payload[k]) for k in sorted(payload)}))
    return {"path": tuple(a.tool for a in trace.actions), "steps": len(trace.actions),
            "visible_shapes": tuple(sorted(visible_shapes)), "firewall_findings": findings}


def _shape(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _shape(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, list):
        return {"length": len(value), "item": _shape(value[0]) if value else None}
    return type(value).__name__


def _canonical(value: Any) -> str:
    def normalized(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: normalized(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normalized(child) for child in item]
        if isinstance(item, bool) or item is None:
            return item
        if isinstance(item, (int, float)):
            return "<NUM>"
        if isinstance(item, str):
            return normalize(item)
        return item

    return json.dumps(normalized(value), sort_keys=True, ensure_ascii=False)


def _structural_features(value: Any, path: str = "$") -> set[str]:
    features: set[str] = set()
    if isinstance(value, Mapping):
        features.add(f"object:{path}")
        for key, child in value.items():
            child_path = f"{path}/{key}"
            features.add(f"key:{child_path}")
            features.update(_structural_features(child, child_path))
    elif isinstance(value, list):
        features.add(f"list:{path}:{len(value)}")
        for index, child in enumerate(value):
            features.update(_structural_features(child, f"{path}/{index}"))
    else:
        features.add(f"type:{path}:{type(value).__name__}")
        normalized = _canonical(value)
        features.update(f"value:{path}:{token}" for token in _TOKEN_RE.findall(normalized))
    return features


def _pointer_value(value: Any, pointer: str) -> Any:
    current = value
    for part in (p.replace("~1", "/").replace("~0", "~") for p in pointer.strip("/").split("/") if p):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def audit(suite: str, version: str) -> dict[str, Any]:
    path = ROOT / "data" / "v5" / "datasets" / suite / version / "cases.jsonl"
    cases = [case_from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()]
    module = load(suite)
    by_pair: dict[str, dict[str, Any]] = defaultdict(dict)
    for case in cases:
        by_pair[case.pair_id][case.arm] = case
    risk = [c for c in cases if c.arm == "RISK"]
    norm = {c.case_id: _canonical(c.world) for c in risk}
    tokens = {cid: set(_TOKEN_RE.findall(text)) for cid, text in norm.items()}
    family = {c.case_id: c.family_id for c in risk}
    exact: dict[str, list[str]] = defaultdict(list)
    for cid, text in norm.items():
        exact[text].append(cid)
    substitution_only = sorted({cid for group in exact.values() if len({family[c] for c in group}) > 1 for cid in group})
    parent = {f: f for f in sorted(set(family.values()))}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    near_pairs = 0
    max_cross = 0.0
    for a, b in itertools.combinations(sorted(tokens), 2):
        if family[a] == family[b]:
            continue
        sim = _jaccard(tokens[a], tokens[b])
        max_cross = max(max_cross, sim)
        if sim >= NEAR_DUP:
            near_pairs += 1
            parent[find(family[a])] = find(family[b])
    risk_components = len({find(f) for f in parent})
    paths: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    recovery_paths: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    paths_by_difficulty: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    evidence_shapes: dict[str, set[str]] = defaultdict(set)
    safe_step_counts: dict[str, list[int]] = defaultdict(list)
    recovery_step_counts: dict[str, list[int]] = defaultdict(list)
    visible_firewall_findings: list[dict[str, Any]] = []
    mechanism_patterns: dict[str, set[str]] = defaultdict(set)
    roles: set[str] = set()
    organizations: set[str] = set()
    family_inventory: dict[str, dict[str, Any]] = {}
    family_subtype: dict[str, str] = {}
    pair_template_by_family: dict[str, list[str]] = defaultdict(list)
    pair_template_tokens: dict[str, set[str]] = {}
    template_pairs: dict[str, list[str]] = defaultdict(list)
    scenario = getattr(module, f"{suite}Scenario")()
    for pair_id, pair in by_pair.items():
        if set(pair) != {"CONTROL", "RISK"}:
            continue
        control, risk_case = pair["CONTROL"], pair["RISK"]
        family = risk_case.family_id
        family_subtype[family] = risk_case.subtype
        template = _canonical({"subtype": risk_case.subtype, "difficulty": risk_case.difficulty,
                               "domain": risk_case.domain,
                               "CONTROL": control.world, "RISK": risk_case.world})
        pair_template_by_family[family].append(template)
        template_pairs[template].append(family)
        slot_record = {
            pointer: {"CONTROL": _pointer_value(control.world, pointer),
                      "RISK": _pointer_value(risk_case.world, pointer)}
            for pointer in risk_case.mechanism_slots
        }
        mechanism_patterns[risk_case.subtype].add(_canonical(slot_record))
        specs = scenario.agents(risk_case.world)
        roles.update(a.role for a in specs)
        organizations.update(a.organization for a in specs)
        info = family_inventory.setdefault(family, {"subtypes": set(), "difficulties": set(), "domains": set(),
                                                     "organizations": set(), "roles": set(), "pairs": 0,
                                                     "mechanism_pattern_hashes": set()})
        info["subtypes"].add(risk_case.subtype)
        info["difficulties"].add(risk_case.difficulty)
        info["domains"].add(risk_case.domain)
        info["organizations"].update(a.organization for a in specs)
        info["roles"].update(a.role for a in specs)
        info["pairs"] += 1
        info["mechanism_pattern_hashes"].add(hashlib.sha256(_canonical(slot_record).encode()).hexdigest())
    family_tokens = {fam: set().union(*(_structural_features(json.loads(row)) for row in rows))
                     for fam, rows in pair_template_by_family.items()}
    for case in risk:
        safe_trace = asyncio.run(_tool_path(case, module, "witness"))
        paths[case.subtype].add(safe_trace["path"])
        paths_by_difficulty[case.difficulty].add(safe_trace["path"])
        evidence_shapes[case.subtype].update(safe_trace["visible_shapes"])
        safe_step_counts[case.difficulty].append(safe_trace["steps"])
        visible_firewall_findings.extend({"case_id": case.case_id, "policy": "witness", **finding}
                                         for finding in safe_trace["firewall_findings"])
        if "recovery" in module.policies():
            recovery_trace = asyncio.run(_tool_path(case, module, "recovery"))
            recovery_paths[case.subtype].add(recovery_trace["path"])
            recovery_step_counts[case.difficulty].append(recovery_trace["steps"])
            visible_firewall_findings.extend({"case_id": case.case_id, "policy": "recovery", **finding}
                                             for finding in recovery_trace["firewall_findings"])
    for family, info in family_inventory.items():
        info["subtypes"] = sorted(info["subtypes"])
        info["difficulties"] = sorted(info["difficulties"])
        info["domains"] = sorted(info["domains"])
        info["organizations"] = sorted(info["organizations"])
        info["roles"] = sorted(info["roles"])
        info["mechanism_pattern_count"] = len(info.pop("mechanism_pattern_hashes"))
        info["pair_template_sha256"] = hashlib.sha256("\n".join(sorted(pair_template_by_family[family])).encode()).hexdigest()
    for threshold in (0.85, 0.90, 0.95):
        roots = {f: f for f in family_tokens}

        def root(x: str) -> str:
            while roots[x] != x:
                roots[x] = roots[roots[x]]
                x = roots[x]
            return x

        for a, b in itertools.combinations(sorted(family_tokens), 2):
            if family_subtype[a] != family_subtype[b]:
                continue
            if _jaccard(family_tokens[a], family_tokens[b]) >= threshold:
                roots[root(a)] = root(b)
        pair_template_tokens[f"{threshold:.2f}"] = {root(f) for f in roots}
    template_exact_duplicates = sorted(sorted(set(group)) for group in template_pairs.values() if len(set(group)) > 1)
    candidate_gate_failures = []
    for pair_id, pair in by_pair.items():
        if set(pair) == {"CONTROL", "RISK"}:
            result = check_pair(pair["CONTROL"], pair["RISK"])
            if not result["passed"]:
                candidate_gate_failures.append({"pair_id": pair_id, "failures": result["failures"]})
    maps = json.loads((ROOT / "contracts" / "v5" / "construct_maps.json").read_text(encoding="utf-8"))
    norm_ids = {x["id"] for x in maps["suites"][suite].get("norms", [])}
    oracle_norms = {str(c.oracle.get("norm")) for c in cases if c.oracle.get("norm")}
    for c in cases:
        oracle_norms.update(map(str, c.oracle.get("norms", [])))
    missing_norms = sorted(oracle_norms - norm_ids)
    subtype_difficulty = Counter((c.subtype, c.difficulty) for c in risk)
    wall = ObservationFirewall()
    diff_violations = sum(bool(pair_diff_violations(p["CONTROL"], p["RISK"])) for p in by_pair.values())
    firewall_hits = sum(bool(wall.scan(dict(c.world))) for c in cases)
    matrix = Counter((c.subtype, c.difficulty) for c in risk)
    return {"suite": suite, "version": version, "cases": len(cases), "pairs": len(by_pair),
            "families": len({c.family_id for c in cases}), "subtypes": sorted({c.subtype for c in cases}),
            "domains": dict(Counter(c.domain for c in risk)), "difficulty": dict(Counter(c.difficulty for c in risk)),
            "subtype_x_difficulty": {f"{s}/{d}": n for (s, d), n in sorted(matrix.items())},
            "entity_substitution_only_cases": len(substitution_only),
            "entity_substitution_only_rate": len(substitution_only) / len(risk) if risk else None,
            "pair_template_exact_duplicate_groups": template_exact_duplicates,
            "pair_template_exact_unique_families": len({hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()
                                                           for rows in pair_template_by_family.values()}),
            "pair_template_effective_family_n_by_jaccard_threshold":
                {threshold: len(roots) for threshold, roots in pair_template_tokens.items()},
            "pair_template_family_n_by_subtype": {subtype: sum(family_subtype[f] == subtype for f in family_tokens)
                                                    for subtype in sorted(set(family_subtype.values()))},
            "risk_world_near_duplicate_pairs_legacy": near_pairs,
            "risk_world_max_cross_family_jaccard_legacy": round(max_cross, 4),
            "risk_world_effective_family_n_legacy": risk_components,
            "scenario_family_inventory": dict(sorted(family_inventory.items())),
            "subtype_x_difficulty_case_counts": {f"{s}/{d}": n for (s, d), n in sorted(subtype_difficulty.items())},
            "role_count": len(roles), "roles": sorted(roles), "organization_count": len(organizations),
            "mechanism_pattern_count_by_subtype": {s: len(v) for s, v in sorted(mechanism_patterns.items())},
            "model_visible_evidence_shape_count_by_subtype": {s: len(v) for s, v in sorted(evidence_shapes.items())},
            "witness_tool_paths_per_subtype": {s: len(v) for s, v in sorted(paths.items())},
            "recovery_tool_paths_per_subtype": {s: len(v) for s, v in sorted(recovery_paths.items())},
            "witness_tool_paths_per_difficulty": {d: len(v) for d, v in sorted(paths_by_difficulty.items())},
            "witness_action_steps_by_difficulty": {d: {"n": len(v), "min": min(v), "mean": round(sum(v) / len(v), 2),
                                                        "max": max(v)} for d, v in sorted(safe_step_counts.items())},
            "recovery_action_steps_by_difficulty": {d: {"n": len(v), "min": min(v), "mean": round(sum(v) / len(v), 2),
                                                           "max": max(v)} for d, v in sorted(recovery_step_counts.items())},
            "pair_diff_violations": diff_violations, "static_firewall_hits": firewall_hits,
            "provider_visible_firewall_findings": visible_firewall_findings,
            "provider_visible_firewall_finding_count": len(visible_firewall_findings),
            "ground_truth_checks": {"every_case_has_oracle": all(bool(c.oracle) for c in cases),
                                    "all_oracle_norm_ids_in_construct_map": not missing_norms,
                                    "missing_norm_ids": missing_norms,
                                    "automated_ambiguity_status": "NO_SCHEMA_OR_REFERENCE_GATE_AMBIGUITY; EXPERT_SEMANTIC_REVIEW_PENDING"},
            "difficulty_evidence_status": "DESIGN_PROXY_ONLY; witness action counts are not empirical model difficulty; pilot required",
            "candidate_gate_failure_count": len(candidate_gate_failures),
            "candidate_gate_failures": candidate_gate_failures,
            "ground_truth_ambiguity_note": "Automated gates confirm witness decidability and reference-policy scorer sensitivity; semantic ambiguity requires Gate D human review."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="5.1.0")
    parser.add_argument("--suites", nargs="*", default=None)
    args = parser.parse_args()
    base = ROOT / "data" / "v5" / "datasets"
    suites = args.suites or sorted(p.name for p in base.iterdir() if (p / args.version / "cases.jsonl").exists())
    reports = [audit(s, args.version) for s in suites]
    out = ROOT / "artifacts" / "v5" / "data_quality" / args.version / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"near_duplicate_threshold": NEAR_DUP, "suites": reports}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"{'suite':6} pairs fam pairN@.90 exactDup subst% paths gateV fw")
    for r in reports:
        exact_duplicates = sum(max(0, len(group) - 1) for group in r["pair_template_exact_duplicate_groups"])
        print(f"{r['suite']:6} {r['pairs']:5} {r['families']:3} "
              f"{r['pair_template_effective_family_n_by_jaccard_threshold']['0.90']:8} {exact_duplicates:8} "
              f"{100 * (r['entity_substitution_only_rate'] or 0):5.1f} "
              f"{sum(r['witness_tool_paths_per_subtype'].values()):5} "
              f"{r['candidate_gate_failure_count']:5} {r['static_firewall_hits']:2}")


if __name__ == "__main__":
    main()
