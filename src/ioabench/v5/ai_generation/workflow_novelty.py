"""Exact, name-independent typed graph identity for the bounded business DAGs.

Only executable dependencies count: edge annotations with identical runtime
semantics do not create families. Frozen workflow_hash values remain untouched.
"""
from __future__ import annotations

import itertools
import json
from collections import defaultdict

from ioabench.hashing import canonical_sha256

VERSION = "ioabench.v5.workflow-graph/1.0.0"


def workflow_graph(binding):
    """Project stages plus role/actor/grant/visibility relations, not their names."""
    value = binding.as_dict() if hasattr(binding, "as_dict") else binding
    steps = value.get("plan") or []
    if not steps:
        tools = {tool["event"]: tool for tool in value.get("tools", [])}
        steps = [{"stage_id": entry["event"], "tool": tools[entry["event"]]["tool"],
                  "capability": tools[entry["event"]]["capability"],
                  "role": next(grant["logical_role"] for grant in value["role_bindings"]
                               if grant["agent_id"] == entry["actor_agent"]
                               and tools[entry["event"]]["tool"] in grant["granted_tools"]),
                  "agent_id": entry["actor_agent"], "requires": entry["requires"],
                  "arguments": {}, "evidence": None}
                 for entry in value.get("event_dag", [])]
    nodes, edges = {}, set()
    grants = value.get("role_bindings", [])
    for step in steps:
        sid = step["stage_id"]
        nodes[sid] = {"capability": step["capability"],
                      "evidence_input": bool(step.get("evidence")),
                      "optional": bool(step.get("when")),
                      "branch_fact": bool(step.get("branch_fact"))}
        for req in step["requires"]:
            edges.add((req, sid, "precedes"))
        for argument in step.get("arguments", {}).values():
            if isinstance(argument, dict) and "$ref" in argument:
                source = argument["$ref"].split(".", 1)[0]
                edges.add((source, sid, "receipt"))
        when = step.get("when")
        if when:
            edges.add((when["stage"], sid, "condition:" + str(when["equals"])))
        visible = next((e["visible_to_roles"] for e in value.get("evidence", [])
                        if e["evidence_id"] == step.get("evidence")), [])
        for other in steps:
            oid = other["stage_id"]
            if sid != oid and step["role"] == other["role"]:
                edges.add((sid, oid, "same_role"))
            if sid != oid and step["agent_id"] == other["agent_id"]:
                edges.add((sid, oid, "same_actor"))
            if any(g["agent_id"] == step["agent_id"] and other["tool"] in g["granted_tools"]
                   for g in grants):
                edges.add((sid, oid, "granted"))
            if other["role"] in visible:
                edges.add((sid, oid, "evidence_visible"))
    return {"version": VERSION, "nodes": nodes, "edges": sorted(edges)}


def canonical_graph(graph):
    """Exhaustive exact labeling within refined color classes (catalog <=12 stages)."""
    nodes, edges = graph["nodes"], graph["edges"]
    labels = {sid: json.dumps(label, sort_keys=True) for sid, label in nodes.items()}

    def colors_of(signatures):
        ranks = {text: rank for rank, text in enumerate(sorted(set(signatures.values())))}
        return {sid: ranks[text] for sid, text in signatures.items()}

    colors = colors_of(labels)
    for _ in nodes:
        signatures = {sid: json.dumps([colors[sid], sorted(
            [("out", kind, colors[b]) for a, b, kind in edges if a == sid] +
            [("in", kind, colors[a]) for a, b, kind in edges if b == sid])]) for sid in nodes}
        refined = colors_of(signatures)
        if len(set(refined.values())) == len(set(colors.values())):
            colors = refined
            break
        colors = refined
    groups = defaultdict(list)
    for sid in nodes:
        groups[colors[sid]].append(sid)
    best, best_order = None, ()
    for parts in itertools.product(*(itertools.permutations(groups[color]) for color in sorted(groups))):
        order = tuple(itertools.chain.from_iterable(parts))
        positions = {sid: index for index, sid in enumerate(order)}
        candidate = (tuple(labels[sid] for sid in order),
                     tuple(sorted((positions[a], positions[b], kind) for a, b, kind in edges)))
        if best is None or candidate < best:
            best, best_order = candidate, order
    return {"version": VERSION, "canonical": best, "order": best_order,
            "family_id": canonical_sha256({"version": VERSION, "canonical": best})}


def isomorphism(left, right):
    """Return a checkable node mapping; compare canonical data, not only its hash."""
    a, b = canonical_graph(left), canonical_graph(right)
    if a["canonical"] != b["canonical"]:
        return None
    return dict(zip(a["order"], b["order"]))
