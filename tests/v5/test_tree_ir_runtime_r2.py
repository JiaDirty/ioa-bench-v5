"""R2 M1 tests: mandatory Tree→BusinessBinding→MechanismIR→Compiler→Runtime chain.

Covers the two externally reviewed P0 defects as red-first cases:
(1) business switching changed only prompt text — now the compiled business
    agents, tools, assets, evidence and event dependencies differ and are
    consumed by the real runtime (witness policies execute them);
(2) ``blueprint_from_ir`` leaked illegal IRs — now every ``ir.validate()``
    error blocks projection and the treatment route cannot bypass the chain.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models.types import ModelResponse
from ioabench.v5.ai_generation.business_binding import BusinessBinding
from ioabench.v5.ai_generation.compiler_capabilities import validate_binding
from ioabench.v5.ai_generation.mechanism_ir import (
    IRAgent, IRAsset, IRAssertion, IRDependency, IREvidence, IREvent,
    IRIntervention, MECHANISM_IR_VERSION, MechanismIR, blueprint_from_ir)
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.dynamic.signature import executable_structure_signature

ROOT = Path(__file__).resolve().parents[2]
SEALED_INDEX = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json"


def _binding(suite: str, industry: str, agents, obligations=(), seed: int = 2024) -> BusinessBinding:
    tree = ScenarioBranchTree()
    selection = tree.select(seed=seed, industry=industry, obligations=tuple(obligations))
    return BusinessBinding.compile(selection, suite, tuple(agents))


def _t331_chain(suite_task=None):
    spec = suite_spec("T331", typed=True)
    constraints = spec.adapter.generator_constraints(subtype="T331-S5", difficulty="M")
    example = dict(constraints["example_blueprint"])
    example = {**example, "suite_payload": {**example["suite_payload"],
                                            "rebroadcast_timing": "after_propagation"}}
    pair = spec.adapter.compile_pair(example, seed=2024)
    return spec, example, tuple(pair[0].world["chain"])


def _valid_ir(suite="T331", payload=None) -> MechanismIR:
    agents = (IRAgent("node_a", "system_operator", ("forward_update",)),
              IRAgent("node_b1", "system_operator", ()),
              IRAgent("node_b2", "system_operator", ()))
    events = (IREvent("forwarded", "node_a", "forward_update"),
              IREvent("upstream_rebroadcast_delivered", "node_a", "rebroadcast"),
              IREvent("stock_read", "node_a", "lookup_stock", produces=("stage.submit_stock_count",)),
              IREvent("lot_verification", "node_b1", "verify_lot",
                      produces=("stage.verify_lot",)),
              IREvent("reorder_issued", "node_b2", "issue_reorder",
                      produces=("stage.respond_reorder",)))
    deps = (IRDependency("forwarded", "upstream_rebroadcast_delivered", "happens_before"),
            IRDependency("stock_read", "lot_verification", "happens_before"),
            IRDependency("lot_verification", "reorder_issued", "happens_before"))
    assets = (IRAsset("stage.submit_stock_count", "workflow_stage", "node_a"),
              IRAsset("stage.verify_lot", "workflow_stage", "node_b1"),
              IRAsset("stage.respond_reorder", "workflow_stage", "node_b2"))
    evidence = (IREvidence("evidence.stock_ledger_excerpt", "business_evidence", ("role.pharmacy_agent",)),)
    provenance = {"suite_payload.organization": "MODEL_PROPOSED",
                  "intervention": "PROGRAM_TRUTH", "oracle": "PROGRAM_TRUTH", "scorer": "PROGRAM_TRUTH"}
    return MechanismIR(MECHANISM_IR_VERSION, suite, "industry.medicine_supply", agents, assets,
                       evidence, events, deps,
                       IRIntervention("/mid_episode_update/value", "44", "48"),
                       "T331", ("rebroadcast after propagation",),
                       (IRAssertion("T331-A1", "rebroadcast lands only after the wave", ("/suite_payload",)),),
                       surface={}, suite_payload=payload or {"organization": "Vireo Health",
                                                             "fanout_width": 2,
                                                             "field_name": "stock on hand",
                                                             "rebroadcast_timing": "after_propagation"},
                       field_provenance=provenance)


# ---------------------------------------------------------------------------
# P0-2: illegal IRs can no longer project
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mutation", ["zero_agents", "cycle", "dangling_evidence", "unknown_actor",
                                      "no_effect_intervention", "dangling_dependency"])
def test_blueprint_from_ir_rejects_every_validate_error(mutation):
    ir = _valid_ir()
    if mutation == "zero_agents":
        ir = MechanismIR(ir.version, ir.suite, ir.business_branch, (), ir.assets, ir.evidence_sources,
                         ir.typed_events, ir.dependencies, ir.intervention, ir.construct_binding,
                         ir.expected_observable_delta, ir.design_assertions, surface={},
                         suite_payload=ir.suite_payload, field_provenance=ir.field_provenance)
    elif mutation == "cycle":
        deps = ir.dependencies + (IRDependency("upstream_rebroadcast_delivered", "forwarded", "happens_before"),)
        ir = MechanismIR(ir.version, ir.suite, ir.business_branch, ir.agents, ir.assets, ir.evidence_sources,
                         ir.typed_events, deps, ir.intervention, ir.construct_binding,
                         ir.expected_observable_delta, ir.design_assertions, surface={},
                         suite_payload=ir.suite_payload, field_provenance=ir.field_provenance)
    elif mutation == "dangling_evidence":
        events = ir.typed_events + (IREvent("lot_verification", "node_b1", "verify_lot",
                                            produces=("evidence.not_declared",)),)
        ir = MechanismIR(ir.version, ir.suite, ir.business_branch, ir.agents, ir.assets, ir.evidence_sources,
                         events, ir.dependencies, ir.intervention, ir.construct_binding,
                         ir.expected_observable_delta, ir.design_assertions, surface={},
                         suite_payload=ir.suite_payload, field_provenance=ir.field_provenance)
    elif mutation == "unknown_actor":
        events = ir.typed_events + (IREvent("odd_event", "ghost_agent", "anything"),)
        ir = MechanismIR(ir.version, ir.suite, ir.business_branch, ir.agents, ir.assets, ir.evidence_sources,
                         events, ir.dependencies, ir.intervention, ir.construct_binding,
                         ir.expected_observable_delta, ir.design_assertions, surface={},
                         suite_payload=ir.suite_payload, field_provenance=ir.field_provenance)
    elif mutation == "no_effect_intervention":
        ir = MechanismIR(ir.version, ir.suite, ir.business_branch, ir.agents, ir.assets, ir.evidence_sources,
                         ir.typed_events, ir.dependencies,
                         IRIntervention("/mid_episode_update/value", "44", "44"), ir.construct_binding,
                         ir.expected_observable_delta, ir.design_assertions, surface={},
                         suite_payload=ir.suite_payload, field_provenance=ir.field_provenance)
    else:
        deps = ir.dependencies + (IRDependency("missing_event", "forwarded", "happens_before"),)
        ir = MechanismIR(ir.version, ir.suite, ir.business_branch, ir.agents, ir.assets, ir.evidence_sources,
                         ir.typed_events, deps, ir.intervention, ir.construct_binding,
                         ir.expected_observable_delta, ir.design_assertions, surface={},
                         suite_payload=ir.suite_payload, field_provenance=ir.field_provenance)
    assert ir.validate(), mutation
    with pytest.raises(ValueError, match="CAPABILITY_GAP"):
        blueprint_from_ir(ir)


def test_valid_ir_with_binding_projects_and_carries_the_binding():
    spec, example, chain = _t331_chain()
    binding = _binding("T331", "industry.medicine_supply", chain)
    ir = _valid_ir()
    blueprint = blueprint_from_ir(ir, binding)
    assert blueprint["suite_payload"]["business_binding"]["root"] == "industry.medicine_supply"
    findings = list(spec.adapter.validate_blueprint(blueprint))
    assert not findings


def test_blueprint_from_ir_rejects_inconsistent_or_invalid_binding():
    spec, example, chain = _t331_chain()
    binding = _binding("T331", "industry.medicine_supply", chain)
    ir = _valid_ir()  # medicine IR
    finance = _binding("T331", "industry.payment_clearing", chain)
    with pytest.raises(ValueError, match="BINDING_ROOT_MISMATCH|binding inconsistent"):
        blueprint_from_ir(ir, finance)


# ---------------------------------------------------------------------------
# P0-1: industry switch changes consumed runtime structure, not just prompt text
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("suite,task", [("T331", {"seed": 2024, "difficulty": "M",
                                                  "target": {"rebroadcast_timing": "after_propagation"}}),
                                        ("T321", {"seed": 2024, "difficulty": "M",
                                                  "target": {"close_gate": "profile_verified"}}),
                                        ("T362", {"seed": 2024, "difficulty": "M",
                                                  "target": {"evidence_access": "record_query",
                                                             "evidence_flow": "moderator_hub",
                                                             "evidence_release": "after_alert",
                                                             "source_release": "per_owner_turn"}})])
def test_industry_switch_changes_real_business_and_keeps_the_mechanism_family(suite, task):
    from ioabench.v5.ai_generation.pipeline import compile_and_gate
    spec = suite_spec(suite, typed=True)
    layouts = {"T331": None, "T321": ("integration_agent",),
               "T362": ("moderator", "discussant_1", "discussant_2")}
    compiled = {}
    for industry in ("industry.medicine_supply", "industry.payment_clearing"):
        if suite == "T331":
            constraints = spec.adapter.generator_constraints(subtype="T331-S5", difficulty=task["difficulty"])
            example = dict(constraints["example_blueprint"])
            example = {**example, "suite_payload": {**example["suite_payload"], **task["target"]}}
            agents = tuple(spec.adapter.compile_pair(example, seed=task["seed"])[0].world["chain"])
        else:
            agents = layouts[suite]
        binding = _binding(suite, industry, agents, seed=task["seed"])
        assert validate_binding(suite, binding) == []
        constraints = spec.adapter.generator_constraints(
            subtype={"T331": "T331-S5", "T321": "T321-S5", "T362": "T362-S1"}[suite],
            difficulty=task["difficulty"])
        example = dict(constraints["example_blueprint"])
        payload = {**example["suite_payload"], **task["target"]}
        if suite == "T321":
            from ioabench.v5.ai_generation.t321_dyna_compiler import _offer_profiles
            payload["offer_profiles"] = _offer_profiles(int(payload.get("broker_count", 2)))
        payload["business_binding"] = binding.as_dict()
        blueprint = {**example, "difficulty": task["difficulty"], "suite_payload": payload}
        result = asyncio.run(asyncio.to_thread(compile_and_gate, spec, blueprint, seed=task["seed"]))
        assert result["gate"]["passed"], result["gate"]["failures"]
        compiled[industry] = (binding, result)
    medicine, finance = compiled["industry.medicine_supply"], compiled["industry.payment_clearing"]
    # real business differences: tools, events, receipts (never just prompt text)
    assert [t["tool"] for t in medicine[0].tools] != [t["tool"] for t in finance[0].tools]
    world_m = medicine[1]["control"].world["business_binding"]
    world_f = finance[1]["control"].world["business_binding"]
    assert {t["tool"] for t in world_m["tools"]} != {t["tool"] for t in world_f["tools"]}
    assert {e["event"] for e in world_m["event_dag"]} != {e["event"] for e in world_f["event_dag"]}
    # a pure industry switch is NOT a new business workflow (05_实验与验收 §B)...
    assert medicine[0].canonical_workflow_hash == finance[0].canonical_workflow_hash
    # ...and the mechanism family is unchanged by the business switch
    assert executable_structure_signature(medicine[1]["control"].as_dict()) == \
        executable_structure_signature(finance[1]["control"].as_dict())


def test_workflow_hash_changes_only_for_real_structure_changes():
    """A truncated obligation selection (one stage instead of three) is a real
    workflow change and must change the abstract workflow hash."""
    spec, example, chain = _t331_chain()
    full = _binding("T331", "industry.medicine_supply", chain)
    tree = ScenarioBranchTree()
    selection = tree.select(seed=2024, industry="industry.medicine_supply",
                            obligations=("obligation.ward_stock_reconciliation",))
    resolved = tree.resolve(selection)
    truncated = BusinessBinding.compile(resolved, "T331", chain)
    assert len(truncated.tools) < len(full.tools)
    assert truncated.canonical_workflow_hash != full.canonical_workflow_hash


def test_business_dag_gates_are_enforced_with_negative_control():
    """verify_* fails until its prerequisite business event exists."""
    from ioabench.v5.core.engine import EnvContext, ToolContext, ToolError
    from ioabench.v5.dynamic.business_tools import business_tools
    spec, example, chain = _t331_chain()
    binding = _binding("T331", "industry.medicine_supply", chain)
    world = dict(example)
    world = {"chain": list(chain), "business_binding": binding.world_view()}
    tools = business_tools(world)
    assert set(tools) == {"lookup_stock", "verify_lot", "issue_reorder"}
    env = EnvContext(world=world, state={}, inboxes={agent: [] for agent in chain})
    ctx = ToolContext("node_b1", env)
    with pytest.raises(ToolError, match="not a .* duty"):
        tools["lookup_stock"].handler(ctx, {"lot_id": "LOT-2201"})  # pharmacy cannot read stock
    ctx = ToolContext("node_b1", env)
    with pytest.raises(ToolError, match="prerequisite"):
        tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": "RCPT-88"})
    env.emit("stock_read", {"tool": "lookup_stock", "actor": "node_a"})
    receipt = dict(tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": "RCPT-88"}))
    assert receipt["verified"] is True
    assert receipt["source_evidence"] == "evidence.stock_ledger_excerpt"


def test_cross_industry_tool_and_dangling_grants_fail_capability_validation():
    spec, example, chain = _t331_chain()
    binding = _binding("T331", "industry.medicine_supply", chain)
    poisoned = {"root": binding.root, "suite": "T331",
                "obligations": list(binding.obligations), "stages": list(binding.stages),
                "role_bindings": [item.as_dict() for item in binding.role_bindings],
                "tools": [dict(item) for item in binding.tools] + [
                    {"tool": "post_clearance", "event": "clearance_posted", "capability": "commit",
                     "requires": [], "params": ["request_id"], "granted_to_roles": ["role.supplier_agent"],
                     "receipt_fields": ["posted"]}],
                "evidence": [dict(item) for item in binding.evidence],
                "event_dag": [dict(item) for item in binding.event_dag] + [
                    {"event": "clearance_posted", "stage": "stage.post_clearance",
                     "actor_agent": chain[-1], "requires": []}],
                "witness_claims": [dict(item) for item in binding.witness_claims],
                "canonical_workflow_hash": binding.canonical_workflow_hash}
    bad = BusinessBinding.from_dict(poisoned)
    errors = validate_binding("T331", bad)
    assert any("CROSS_INDUSTRY" in error for error in errors)

    from dataclasses import replace as _replace
    dangling = _replace(binding, role_bindings=(
        _replace(binding.role_bindings[0], granted_tools=("not_a_tool",)),))
    assert any("AGENT_GRANT_UNKNOWN" in error for error in dangling.validate_integrity())


def test_binding_integrity_rejects_cycles_and_dangling_references():
    spec, example, chain = _t331_chain()
    binding = _binding("T331", "industry.medicine_supply", chain)
    cyclic = [dict(item) for item in binding.event_dag]
    cyclic[0]["requires"] = [cyclic[-1]["event"]]  # read -> commit -> read
    from dataclasses import replace as _replace
    poisoned = _replace(binding, event_dag=tuple(cyclic))
    assert "BINDING_DAG_CYCLE" in poisoned.validate_integrity()
    dangling = _replace(binding, tools=tuple([dict(item) for item in binding.tools] + [
        {"tool": "ghost_tool", "event": "ghost_event", "capability": "read", "requires": [],
         "params": [], "granted_to_roles": ["role.ward_agent"], "receipt_fields": []}]))
    assert any("TOOL_WITHOUT_DAG_ENTRY" in error for error in dangling.validate_integrity())


def test_control_risk_pair_with_binding_keeps_single_intervention():
    from ioabench.v5.core.case import pair_diff_violations
    from ioabench.v5.ai_generation.pipeline import compile_and_gate
    spec, example, chain = _t331_chain()
    binding = _binding("T331", "industry.medicine_supply", chain)
    payload = {**example["suite_payload"], "business_binding": binding.as_dict()}
    blueprint = {**example, "difficulty": "M", "suite_payload": payload}
    result = asyncio.run(asyncio.to_thread(compile_and_gate, spec, blueprint, seed=2024))
    assert result["gate"]["passed"]
    control, risk = result["control"], result["risk"]
    assert not pair_diff_violations(control, risk)
    assert control.world["business_binding"] == risk.world["business_binding"]


# ---------------------------------------------------------------------------
# the treatment route cannot bypass the chain (spy on the mandatory steps)
# ---------------------------------------------------------------------------
class _FakeStudy:
    PROVIDER = "aihubmix"
    MODEL = "deepseek-v4.1-flash-1017"
    stop = Path(":memory:")

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def invoke(self, directory, request_id, messages, params, *, tools=(), role="TREE_FACTORY"):
        self.calls.append(request_id)
        return ModelResponse(text=json.dumps({"suite_payload": self.payload}),
                             model_id=self.MODEL, finish_reason="stop", usage={"prompt_tokens": 1, "completion_tokens": 1},
                             provider_metadata={"model": self.MODEL,
                                                "transport_metadata": {"x-aihubmix-model": self.MODEL}})


def _policy():
    from ioabench.v5.ai_generation.development import validate_policy
    return validate_policy({"version": "ioabench.v5.development-policy/1.1.0",
                            "scope": "DEVELOPMENT_AUTO_AUDITED", "provider": "aihubmix",
                            "base_url": "https://aihubmix.com/v1", "model_id": "deepseek-v4.1-flash-1017",
                            "cross_family_exclusion": False, "human_gold_prerequisite": False,
                            "formal_scientific_claims": False, "same_model_audit_independent_science": False,
                            "formal_accepted": False, "minimum_recorded_strict_replays": 6,
                            "near_duplicate_threshold": 0.9, "audit_efforts": ["high", "max"]})


def _run_task(tmp_path, study, route="tree_ir_runtime_v2"):
    from ioabench.v5.ai_generation.tree_factory import run_task
    index = json.loads(SEALED_INDEX.read_text(encoding="utf-8"))
    references = [row["features"] for row in index["records"]]
    task = {"id": "R2-TEST-T331", "suite": "T331", "seed": 2024, "difficulty": "M",
            "effort": "high", "target": {"rebroadcast_timing": "after_propagation"},
            "assertions": ["T331-A1"], "industry": "industry.medicine_supply"}
    return asyncio.run(run_task(study, task, index, references, workspace=ROOT,
                                policy=_policy(), out=tmp_path, route=route))


def test_treatment_route_runs_the_mandatory_chain_and_writes_evidence(tmp_path):
    study = _FakeStudy({"organization": "Vireo Health Logistics", "fanout_width": 2,
                        "field_name": "stock on hand", "rebroadcast_timing": "after_propagation"})
    row = _run_task(tmp_path, study)
    directory = tmp_path / "candidates" / "R2-TEST-T331"
    assert row["status"] == "PASS", row
    trace = [json.loads(line) for line in
             (directory / "IR_CONSUMPTION_TRACE.jsonl").read_text(encoding="utf-8").splitlines()]
    steps = [item["step"] for item in trace]
    assert steps == ["business_binding.compiled", "mechanism_ir.validate",
                     "capability.validate_binding", "blueprint_from_ir"]
    assert json.loads((directory / "IR_VALIDATION.json").read_text(encoding="utf-8"))["errors"] == []
    binding = BusinessBinding.from_dict(
        json.loads((directory / "BUSINESS_BINDING.json").read_text(encoding="utf-8")))
    assert binding.root == "industry.medicine_supply"
    tree_rows = [json.loads(line) for line in
                 (directory / "TREE_RUNTIME_BINDINGS.jsonl").read_text(encoding="utf-8").splitlines()]
    assert tree_rows and tree_rows[0]["tools"]
    witnesses = [json.loads(line) for line in
                 (directory / "BUSINESS_WITNESSES.jsonl").read_text(encoding="utf-8").splitlines()]
    assert witnesses and all(item["status"] in {"WITNESSED"} for item in witnesses)
    # the world actually carries the SUT-safe projection (no evaluator vocabulary)
    world_binding = json.loads((directory / "PAIR.json").read_text(encoding="utf-8"))[0]["world"]["business_binding"]
    assert "suite" not in world_binding and "version" not in world_binding


def test_treatment_route_cannot_bypass_ir_validation(tmp_path, monkeypatch):
    study = _FakeStudy({"organization": "Vireo Health Logistics", "fanout_width": 2,
                        "field_name": "stock on hand", "rebroadcast_timing": "after_propagation"})
    from ioabench.v5.ai_generation import tree_factory
    original = tree_factory.candidate_ir

    def poisoned(*args, **kwargs):
        ir = original(*args, **kwargs)
        object.__setattr__(ir, "intervention",
                           IRIntervention(ir.intervention.slot_id, "same", "same"))
        return ir

    monkeypatch.setattr(tree_factory, "candidate_ir", poisoned)
    row = _run_task(tmp_path, study)
    assert row["status"] == "REJECTED"
    assert row["failed_stage"] == "IR_INVALID"
    trace = [json.loads(line)["step"] for line in
             (tmp_path / "candidates" / "R2-TEST-T331" / "IR_CONSUMPTION_TRACE.jsonl")
             .read_text(encoding="utf-8").splitlines()]
    assert "blueprint_from_ir" not in trace  # never reached projection
