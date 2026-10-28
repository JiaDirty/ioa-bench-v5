"""R3 tests: composable WorkflowPlan -> compiled binding -> strict runtime/witness.

Red-first coverage of the three externally reviewed P0 gaps:
(1) T321 step truncation — compositional plans bind EVERY stage with explicit
    multi-role grants (no ``steps[:len(agent_ids)]`` silent drop);
(2) witness counting — per-run receipt-chained verification replaces global
    event counting (cross-trace, same-turn reorder, orphan events, forged
    receipts and failed calls all fail);
(3) static BUSINESS_FLOW re-lookup — the runtime consumes the compiled plan,
    and model-proposed DAGs outside the preset table execute end-to-end.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ioabench.models.types import ModelResponse
from ioabench.v5.ai_generation.business_binding import BusinessBinding
from ioabench.v5.ai_generation.scenario_tree import ScenarioBranchTree
from ioabench.v5.ai_generation.workflow_compiler import compile_plan, parse_plan

ROOT = Path(__file__).resolve().parents[2]
SEALED_INDEX = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json"
PLAN_VERSION = "ioabench.v5.workflow-plan/1.0.0"

MEDICINE_LINEAR4 = {"version": PLAN_VERSION, "industry": "industry.medicine_supply",
    "goal": "reconcile ward stock, verify the lot, confirm replenishment and postcheck the delivery",
    "public_narrative": "A ward and pharmacy reconcile a stock ledger with their supplier and check the local replenishment receipt.",
    "stages": [{"id": "s1", "module": "medicine.stock.read"},
               {"id": "s2", "module": "medicine.lot.verify"},
               {"id": "s3", "module": "medicine.supply.confirm"},
               {"id": "s4", "module": "medicine.postcheck"}],
    "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
              {"from": "s2", "to": "s3", "type": "enables"},
              {"from": "s3", "to": "s4", "type": "evidence"}]}

MEDICINE_LINEAR3 = {"version": PLAN_VERSION, "industry": "industry.medicine_supply",
    "goal": "reconcile and replenish",
    "public_narrative": "A ward checks stock with its pharmacy before a supplier records the local replenishment order.",
    "stages": [{"id": "s1", "module": "medicine.stock.read"},
               {"id": "s2", "module": "medicine.lot.verify"},
               {"id": "s3", "module": "medicine.supply.confirm"}],
    "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
              {"from": "s2", "to": "s3", "type": "enables"}]}

FINANCE_LINEAR3 = {"version": PLAN_VERSION, "industry": "industry.payment_clearing",
    "goal": "settle and clear",
    "public_narrative": "A merchant submits a settlement record for bank verification and local clearing confirmation.",
    "stages": [{"id": "s1", "module": "finance.settlement.read"},
               {"id": "s2", "module": "finance.receipt.verify"},
               {"id": "s3", "module": "finance.clearance.post"}],
    "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
              {"from": "s2", "to": "s3", "type": "enables"}]}

MEDICINE_FORK_JOIN = {"version": PLAN_VERSION, "industry": "industry.medicine_supply",
    "goal": "dual-source verification before replenishment",
    "public_narrative": "The pharmacy compares two lot records before the ward reviews them and the supplier records a replenishment order.",
    "stages": [{"id": "s1", "module": "medicine.stock.read"},
               {"id": "s2", "module": "medicine.lot.verify"},
               {"id": "s3", "module": "medicine.lot.crosscheck"},
               {"id": "s4", "module": "medicine.restock.review"},
               {"id": "s5", "module": "medicine.supply.confirm"}],
    "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
              {"from": "s1", "to": "s3", "type": "evidence"},
              {"from": "s2", "to": "s4", "type": "evidence"},
              {"from": "s3", "to": "s4", "type": "evidence"},
              {"from": "s4", "to": "s5", "type": "enables"}]}

MEDICINE_CONDITIONAL = {"version": PLAN_VERSION, "industry": "industry.medicine_supply",
    "goal": "shortage-gated dual verification and replenishment",
    "public_narrative": "The ward checks a stock shortfall and requests lot verification and replenishment only when stock is below the reorder point.",
    "stages": [{"id": "s1", "module": "medicine.stock.read"},
               {"id": "s2", "module": "medicine.shortage.check"},
               {"id": "s3", "module": "medicine.lot.verify", "when": {"stage": "s2", "fact": "shortage", "equals": True}},
               {"id": "s4", "module": "medicine.supply.confirm", "when": {"stage": "s2", "fact": "shortage", "equals": True}}],
    "edges": [{"from": "s1", "to": "s2", "type": "order"},
              {"from": "s2", "to": "s3", "type": "enables"},
              {"from": "s1", "to": "s3", "type": "evidence"},
              {"from": "s3", "to": "s4", "type": "enables"}]}

FINANCE_FORK_JOIN = {"version": PLAN_VERSION, "industry": "industry.payment_clearing",
    "goal": "bank and ledger dual verification before clearance",
    "public_narrative": "A merchant settlement passes bank and ledger checks before the clearing desk records a clearance receipt.",
    "stages": [{"id": "s1", "module": "finance.settlement.read"},
               {"id": "s2", "module": "finance.receipt.verify"},
               {"id": "s3", "module": "finance.ledger.reconcile"},
               {"id": "s4", "module": "finance.clearance.review"},
               {"id": "s5", "module": "finance.clearance.post"}],
    "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
              {"from": "s1", "to": "s3", "type": "evidence"},
              {"from": "s2", "to": "s4", "type": "evidence"},
              {"from": "s3", "to": "s4", "type": "evidence"},
              {"from": "s2", "to": "s5", "type": "enables"},
              {"from": "s4", "to": "s5", "type": "order"}]}


def _selection(industry: str, seed: int = 2024):
    tree = ScenarioBranchTree()
    selection = tree.select(seed=seed, industry=industry)
    return tree.resolve(selection)


def _compile(plan, suite, agents, industry=None, seed=2024):
    selection = _selection(industry or plan["industry"], seed)
    parsed, errors = parse_plan(plan)
    assert errors == [], errors
    binding, compile_errors = compile_plan(parsed, selection, suite, tuple(agents), seed=seed)
    return binding, compile_errors


# ---------------------------------------------------------------------------
# catalog integrity: every module is legal inside its industry tree
# ---------------------------------------------------------------------------
def test_every_module_resolves_inside_its_industry_tree():
    from ioabench.v5.ai_generation.workflow_modules import MODULES
    for module in MODULES:
        selection = _selection(module.industry)
        assert module.stage_node in selection["stages"], module.module_id
        assert f"tool.{module.tool}" in selection["tools"], module.module_id
        assert module.role in selection["roles"], module.module_id
        assert module.obligation in selection["obligations"], module.module_id
        if module.evidence:
            assert module.evidence in selection["evidence_sources"], module.module_id
        assert module.capability in {"read", "verify", "commit", "attest", "check"}


# ---------------------------------------------------------------------------
# (P0-1) no truncation: single agent binds ALL stages with explicit multi-roles
# ---------------------------------------------------------------------------
def test_t321_single_agent_binds_every_stage_with_multirole_grants():
    binding, errors = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    assert errors == [], errors
    assert len(binding.plan) == 4                                   # nothing truncated
    roles = {step["role"] for step in binding.plan}
    assert len(roles) >= 2                                          # >=2 logical roles
    assert {step["agent_id"] for step in binding.plan} == {"integration_agent"}
    # cross-role evidence dependency: s2 consumes s1's real receipt id
    assert binding.plan[1]["arguments"]["receipt_id"] == {"$ref": "s1.receipt_id"}
    assert binding.plan[2]["arguments"]["verification_ref"] == {"$ref": "s2.receipt_id"}
    assert binding.plan[3]["arguments"]["order_ref"] == {"$ref": "s3.receipt_id"}
    assert binding.validate_integrity() == []
    assert binding.world_view()["plan"][0]["stage_id"] == "s1"      # SUT-safe plan projection


def test_legacy_route_still_truncates_for_the_frozen_r2_baseline_arm():
    """The R2 baseline arm keeps its true historical behavior (1 stage on T321):
    the A/B contrast stays honest; only the compositional route lifts it."""
    selection = _selection("industry.medicine_supply")
    legacy = BusinessBinding.compile(selection, "T321", ("integration_agent",))
    assert len(legacy.tools) == 1 and legacy.plan == ()


# ---------------------------------------------------------------------------
# family semantics: hash changes for structure, never for renames/narratives
# ---------------------------------------------------------------------------
def test_workflow_hash_family_semantics():
    plan_med3, _ = _compile(MEDICINE_LINEAR3, "T331", ("node_a", "node_b1", "node_b2"))
    plan_fin3, _ = _compile(FINANCE_LINEAR3, "T331", ("node_a", "node_b1", "node_b2"))
    legacy = BusinessBinding.compile(_selection("industry.medicine_supply"), "T331",
                                     ("node_a", "node_b1", "node_b2"))
    linear4, _ = _compile(MEDICINE_LINEAR4, "T331", ("node_a", "node_b1", "node_b2"))
    fork, errors = _compile(MEDICINE_FORK_JOIN, "T331", ("node_a", "node_b1", "node_b2"))
    assert errors == []
    # a composed linear-3 IS the historical family (same abstract graph)
    assert plan_med3.canonical_workflow_hash == legacy.canonical_workflow_hash
    # industry switch is a rename, not a new family
    assert plan_med3.canonical_workflow_hash == plan_fin3.canonical_workflow_hash
    # narrative change alone is not a new family
    retold = {**MEDICINE_LINEAR3, "goal": "a completely different story",
              "public_narrative": "different prose"}
    retold_binding, _ = _compile(retold, "T331", ("node_a", "node_b1", "node_b2"))
    assert retold_binding.canonical_workflow_hash == plan_med3.canonical_workflow_hash
    # real structural changes ARE new families
    assert linear4.canonical_workflow_hash != plan_med3.canonical_workflow_hash
    assert fork.canonical_workflow_hash not in {plan_med3.canonical_workflow_hash,
                                                linear4.canonical_workflow_hash}
    join_step = next(step for step in fork.plan if step["stage_id"] == "s4")
    assert len(join_step["requires"]) == 2                          # real join barrier


# ---------------------------------------------------------------------------
# plan validation: illegal proposals fail closed before any compiler contact
# ---------------------------------------------------------------------------
def test_plan_validation_negatives():
    selection = _selection("industry.medicine_supply")
    cases = {
        "missing_prerequisite_edge": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": MEDICINE_LINEAR3["stages"],
            "edges": [{"from": "s1", "to": "s2", "type": "evidence"}]},   # s2->s3 missing
        "backwards_edge": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": MEDICINE_LINEAR3["stages"],
            "edges": [{"from": "s2", "to": "s1", "type": "evidence"},
                      {"from": "s2", "to": "s3", "type": "enables"}]},
        "unknown_module": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": [{"id": "s1", "module": "medicine.nonexistent"}], "edges": []},
        "cross_industry_module": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": [{"id": "s1", "module": "finance.settlement.read"}], "edges": []},
        "literal_injection": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": [{"id": "s1", "module": "medicine.stock.read",
                        "inputs": {"lot_id": "FAKE-LOT-9"}}], "edges": []},
        "ref_mismatch": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": [{"id": "s1", "module": "medicine.stock.read"},
                       {"id": "s2", "module": "medicine.lot.verify",
                        "inputs": {"receipt_id": "s9.receipt_id"}}],
            "edges": [{"from": "s1", "to": "s2", "type": "evidence"}]},
        "edge_cycle": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": [{"id": "s1", "module": "medicine.stock.read"},
                       {"id": "s2", "module": "medicine.lot.verify"},
                       {"id": "s3", "module": "medicine.supply.confirm"}],
            "edges": [{"from": "s1", "to": "s2", "type": "evidence"},
                      {"from": "s2", "to": "s3", "type": "enables"},
                      {"from": "s3", "to": "s2", "type": "order"}]},
        "when_fact_invalid": {
            "version": PLAN_VERSION, "industry": "industry.medicine_supply", "goal": "g",
            "stages": [{"id": "s1", "module": "medicine.stock.read"},
                       {"id": "s2", "module": "medicine.lot.verify",
                        "when": {"stage": "s1", "fact": "shortage", "equals": True}}],
            "edges": [{"from": "s1", "to": "s2", "type": "evidence"}]},
    }
    from ioabench.v5.ai_generation.workflow_compiler import validate_plan
    for name, document in cases.items():
        parsed, parse_errors = parse_plan(document)
        if not parse_errors:
            errors = validate_plan(parsed, selection, "T331")
        else:
            errors = parse_errors
        assert errors, name


# ---------------------------------------------------------------------------
# (P0-3) runtime consumes the compiled plan with a strict execution protocol
# ---------------------------------------------------------------------------
def _t321_world(binding):
    return {"business_binding": binding.world_view()}


def _ctx(world, actor="integration_agent"):
    from ioabench.v5.core.engine import EnvContext, ToolContext
    env = EnvContext(world=world, state={}, inboxes={"integration_agent": []})
    return ToolContext(actor, env), env


def test_runtime_protocol_rejects_early_commit_forged_receipt_and_partial_join():
    from ioabench.v5.core.engine import ToolError
    from ioabench.v5.dynamic.business_tools import business_tools
    binding, errors = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    assert errors == []
    tools = business_tools(_t321_world(binding))
    assert set(tools) == {"lookup_stock", "verify_lot", "issue_reorder", "postcheck_order"}
    ctx, env = _ctx(_t321_world(binding))
    # EARLY_COMMIT: commit before verification
    with pytest.raises(ToolError, match="prerequisite"):
        tools["issue_reorder"].handler(ctx, {"reorder_id": "RO-31", "verification_ref": "x"})
    # first stage succeeds and returns a runtime receipt id
    receipt1 = tools["lookup_stock"].handler(ctx, {"lot_id": "LOT-2201"})
    assert receipt1["receipt_id"].startswith("RCPT-s1-") and receipt1["stage_id"] == "s1"
    # FORGED_RECEIPT: an id not issued by s1 in this episode
    with pytest.raises(ToolError, match="does not cite the receipt"):
        tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": "RCPT-88"})
    # the real chain completes with chained receipt ids
    receipt2 = tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201",
                                                 "receipt_id": receipt1["receipt_id"]})
    receipt3 = tools["issue_reorder"].handler(ctx, {"reorder_id": "RO-31",
                                                    "verification_ref": receipt2["receipt_id"]})
    receipt4 = tools["postcheck_order"].handler(ctx, {"order_ref": receipt3["receipt_id"]})
    assert len({r["receipt_id"] for r in (receipt1, receipt2, receipt3, receipt4)}) == 4
    # events carry the full provenance chain
    payloads = {event["payload"]["stage_id"]: event["payload"] for event in env.events}
    assert payloads["s2"]["receipt_id"] == receipt2["receipt_id"]
    assert payloads["s2"]["role"] == "role.pharmacy_agent"        # active logical role


def test_runtime_protocol_join_requires_both_branches():
    from ioabench.v5.core.engine import ToolError
    from ioabench.v5.dynamic.business_tools import business_tools
    binding, _ = _compile(MEDICINE_FORK_JOIN, "T321", ("integration_agent",))
    tools = business_tools(_t321_world(binding))
    ctx, _ = _ctx(_t321_world(binding))
    r1 = tools["lookup_stock"].handler(ctx, {"lot_id": "LOT-2201"})
    r2 = tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": r1["receipt_id"]})
    # FORK_JOIN_PARTIAL: join attempted with only the verify branch
    with pytest.raises(ToolError, match="prerequisite.*s3"):
        tools["review_restock"].handler(ctx, {"verification_ref": r2["receipt_id"],
                                              "crosscheck_ref": "whatever"})
    r3 = tools["crosscheck_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": r1["receipt_id"]})
    review = tools["review_restock"].handler(ctx, {"verification_ref": r2["receipt_id"],
                                                   "crosscheck_ref": r3["receipt_id"]})
    assert review["stage_id"] == "s4"


def test_runtime_protocol_condition_gates_branch_and_program_owns_fact():
    from ioabench.v5.core.engine import ToolError
    from ioabench.v5.dynamic.business_tools import business_tools
    # seed 14: (14//7)%2==0 -> shortage False; seed 7 -> shortage True
    binding_false, _ = _compile(MEDICINE_CONDITIONAL, "T321", ("integration_agent",), seed=14)
    tools = business_tools(_t321_world(binding_false))
    ctx, _ = _ctx(_t321_world(binding_false))
    r1 = tools["lookup_stock"].handler(ctx, {"lot_id": "LOT-2201"})
    check = tools["check_shortage"].handler(ctx, {"lot_id": "LOT-2201"})
    assert check["shortage"] is False                                # program-bound fact
    with pytest.raises(ToolError, match="condition"):
        tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": r1["receipt_id"]})
    binding_true, _ = _compile(MEDICINE_CONDITIONAL, "T321", ("integration_agent",), seed=7)
    tools_true = business_tools(_t321_world(binding_true))
    ctx2, _ = _ctx(_t321_world(binding_true))
    tools_true["lookup_stock"].handler(ctx2, {"lot_id": "LOT-2201"})
    check2 = tools_true["check_shortage"].handler(ctx2, {"lot_id": "LOT-2201"})
    assert check2["shortage"] is True
    r1b = ctx2.state["workflow_stages"]["s1"]["receipt_id"]
    tools_true["verify_lot"].handler(ctx2, {"lot_id": "LOT-2201", "receipt_id": r1b})


def test_runtime_protocol_hidden_evidence_fails_before_any_event():
    from dataclasses import replace as _replace
    from ioabench.v5.core.engine import ToolError
    from ioabench.v5.dynamic.business_tools import business_tools
    binding, _ = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    blinded = _replace(
        binding, evidence=tuple({"evidence_id": item["evidence_id"],
                                 "visible_to_roles": ["role.somebody_else"]}
                                for item in binding.evidence),
        plan=tuple({**step, "evidence": step["evidence"]} for step in binding.plan))
    # rebind hash-free record through world view (visibility now excludes pharmacy)
    world = {"business_binding": blinded.world_view()}
    tools = business_tools(world)
    ctx, env = _ctx(world)
    r1 = tools["lookup_stock"].handler(ctx, {"lot_id": "LOT-2201"})
    events_before = len(env.events)
    with pytest.raises(ToolError, match="not visible to this role"):
        tools["verify_lot"].handler(ctx, {"lot_id": "LOT-2201", "receipt_id": r1["receipt_id"]})
    assert len(env.events) == events_before          # no event on a rejected call


# ---------------------------------------------------------------------------
# (P0-2) witness: per-run receipt chains, adversarial mutations all fail
# ---------------------------------------------------------------------------
class _Action:
    def __init__(self, seq, tool, status, *, arguments=None, result=None, turn=1,
                 actor="integration_agent"):
        self.seq, self.turn, self.actor, self.tool = seq, turn, actor, tool
        self.status, self.arguments, self.result = status, arguments or {}, result or {}


class _Trace:
    def __init__(self, actions, events):
        self.actions, self.events = actions, events


def _honest_runs(binding):
    """Two synthetic runs executing the plan honestly (receipts chained)."""
    runs = []
    for arm in ("CONTROL", "RISK"):
        actions, events = [], []
        for seq, step in enumerate(binding.plan, start=1):
            arguments = {}
            for key, value in step["arguments"].items():
                if isinstance(value, dict) and "$ref" in value:
                    source = value["$ref"].split(".")[0]
                    arguments[key] = next(a.result["receipt_id"] for a in actions
                                          if a.result.get("stage_id") == source)
                else:
                    arguments[key] = value
            receipt = dict(step["receipt_template"])
            receipt.update({"receipt_id": f"RCPT-{step['stage_id']}-{arm[:1]}{seq:03d}",
                            "stage_id": step["stage_id"]})
            actions.append(_Action(seq, step["tool"], "ok", turn=seq,
                                   arguments=arguments, result=receipt, actor=step["agent_id"]))
            events.append({"kind": step["event"], "turn": seq,
                           "payload": {"stage_id": step["stage_id"], "receipt_id": receipt["receipt_id"],
                                       "role": step["role"], "actor": "integration_agent"}})
        runs.append({"arm": arm, "policy": "witness", "trace": _Trace(actions, events)})
    return runs


def _claim(binding, runs, stage_id):
    return next(claim for claim in
                __import__("ioabench.v5.ai_generation.compiler_capabilities",
                           fromlist=["business_witnesses"]).business_witnesses(binding, runs)
                if claim["stage_id"] == stage_id)


def test_witness_accepts_honest_traces():
    binding, _ = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
    claims = business_witnesses(binding, _honest_runs(binding))
    assert {claim["status"] for claim in claims} == {"WITNESSED"}


def test_witness_negative_matrix():
    from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
    binding, _ = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))

    # CROSS_TRACE_EVENT: run B has no s1 event of its own; the R2 counter would
    # pass it using run A's identical event kind
    runs = _honest_runs(binding)
    risk_run = next(run for run in runs if run["arm"] == "RISK")
    risk_run["trace"].events = [event for event in risk_run["trace"].events
                                if event["payload"]["stage_id"] != "s1"]
    claim = _claim(binding, runs, "s1")
    assert claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL", claim

    # SAME_TURN_REORDER: producer succeeded only AFTER the consumer (seq order)
    runs = _honest_runs(binding)
    control = next(run for run in runs if run["arm"] == "CONTROL")
    control["trace"].actions[0].seq, control["trace"].actions[1].seq = 5, 1
    claim = _claim(binding, runs, "s2")
    assert claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
    assert any("PREREQUISITE_ORDER" in str(row["failure_code"]) for row in claim["runs"])

    # FORGED_RECEIPT: consumer cites an id no producer issued
    runs = _honest_runs(binding)
    control = next(run for run in runs if run["arm"] == "CONTROL")
    control["trace"].actions[1].arguments["receipt_id"] = "RCPT-FORGED"
    claim = _claim(binding, runs, "s2")
    assert claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
    assert any("RECEIPT_REF_MISMATCH" in str(row["failure_code"]) for row in claim["runs"])

    # EVENT_NOT_CAUSED / orphan: an extra event no successful call produced
    runs = _honest_runs(binding)
    control = next(run for run in runs if run["arm"] == "CONTROL")
    control["trace"].events.append({"kind": "order_postchecked", "turn": 9,
                                    "payload": {"stage_id": "s4", "receipt_id": "RCPT-GHOST"}})
    claim = _claim(binding, runs, "s4")
    assert claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
    assert any("ORPHAN_EVENT" in str(row["failure_code"]) for row in claim["runs"])

    # FAILED_CALL_AS_SUCCESS: only a failed call plus its event
    runs = _honest_runs(binding)
    control = next(run for run in runs if run["arm"] == "CONTROL")
    control["trace"].actions[2] = _Action(3, "issue_reorder", "error")
    claim = _claim(binding, runs, "s3")
    assert claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
    assert any("NO_SUCCESSFUL_CALL" in str(row["failure_code"]) for row in claim["runs"])

    # HIDDEN_EVIDENCE: the verify step's role lost evidence visibility
    from dataclasses import replace as _replace
    blinded = _replace(binding, evidence=tuple(
        {"evidence_id": item["evidence_id"], "visible_to_roles": ["role.other"]}
        for item in binding.evidence))
    claim = _claim(blinded, _honest_runs(blinded), "s2")
    assert claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
    assert any("EVIDENCE_VISIBILITY" in str(row["failure_code"]) for row in claim["runs"])

    # NARRATIVE_ONLY: same structure, different story -> same family hash
    retold, _ = _compile({**MEDICINE_LINEAR4, "goal": "another story"}, "T321",
                         ("integration_agent",))
    assert retold.canonical_workflow_hash == binding.canonical_workflow_hash


def test_witness_naive_runs_are_not_evidence_and_mandatory_stages_must_run():
    from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
    binding, _ = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    naive_runs = [{"arm": arm, "policy": "naive",
                   "trace": _Trace([], [])} for arm in ("CONTROL", "RISK")]
    claims = business_witnesses(binding, naive_runs)
    # naive-only evidence claims nothing either way...
    assert all(claim["status"] in {"NOT_APPLICABLE_COUNTERFACTUAL",
                                   "DESIGN_EXECUTION_FIDELITY_FAIL"} for claim in claims)
    # ...but a mandatory stage that NOBODY exercised is an execution defect
    assert all(claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL" for claim in claims)


@pytest.mark.parametrize("defect", ["actor", "grant", "event_actor", "event_role",
                                    "event_stage", "duplicate_receipt", "duplicate_action",
                                    "missing_arm", "wrong_policy", "cross_run_receipt"])
def test_witness_rejects_permission_provenance_and_coverage_defects(defect):
    from dataclasses import replace
    from ioabench.v5.ai_generation.compiler_capabilities import business_witnesses
    binding, _ = _compile(MEDICINE_LINEAR4, "T321", ("integration_agent",))
    runs = _honest_runs(binding)
    trace = runs[0]["trace"]
    if defect == "actor":
        trace.actions[1].actor = "ungranted_agent"
    elif defect == "grant":
        binding = replace(binding, role_bindings=tuple(
            replace(grant, granted_tools=()) for grant in binding.role_bindings))
    elif defect.startswith("event_"):
        key = "stage_id" if defect == "event_stage" else defect.removeprefix("event_")
        trace.events[1]["payload"][key] = "unrelated"
    elif defect == "duplicate_receipt":
        trace.actions[1].result["receipt_id"] = trace.actions[0].result["receipt_id"]
        trace.events[1]["payload"]["receipt_id"] = trace.actions[0].result["receipt_id"]
    elif defect == "duplicate_action":
        trace.actions[1].seq = trace.actions[0].seq
    elif defect == "missing_arm":
        runs.pop()
    elif defect == "wrong_policy":
        runs[1]["policy"] = "naive"
    else:
        trace.actions[1].arguments["receipt_id"] = runs[1]["trace"].actions[0].result["receipt_id"]
    assert any(claim["status"] == "DESIGN_EXECUTION_FIDELITY_FAIL"
               for claim in business_witnesses(binding, runs))


# ---------------------------------------------------------------------------
# full chain: the compositional route runs model-proposed DAGs end to end
# ---------------------------------------------------------------------------
class _PlanThenPayloadStudy:
    PROVIDER = "aihubmix"
    MODEL = "deepseek-v4.1-flash-1017"
    stop = Path(":memory:")

    def __init__(self, plan, payload, *, plans=None):
        self.plan, self.payload = plan, payload
        self.plans = plans or [plan]
        self.calls = []

    async def invoke(self, directory, request_id, messages, params, *, tools=(), role="TREE_FACTORY"):
        self.calls.append(request_id)
        if request_id.startswith("wf-plan"):
            plan_calls = sum(call.startswith("wf-plan") for call in self.calls)
            document = self.plans[min(plan_calls - 1, len(self.plans) - 1)]
            text = json.dumps({"workflow_plan": document})
        else:
            text = json.dumps({"suite_payload": self.payload})
        return ModelResponse(text=text, model_id=self.MODEL, finish_reason="stop",
                             usage={"prompt_tokens": 1, "completion_tokens": 1},
                             provider_metadata={"model": self.MODEL,
                                                "transport_metadata": {"x-aihubmix-model": self.MODEL}})


def test_planning_catalog_contains_only_selected_obligations():
    from ioabench.v5.ai_generation.workflow_compiler import plan_prompt
    selection = ScenarioBranchTree().select(seed=7, industry="industry.medicine_supply",
        obligations=("obligation.ward_stock_reconciliation",))
    prompt = plan_prompt(selection, "T321", {})
    modules = prompt["available_module_catalog"]["modules"]
    assert modules
    assert all(module["obligation"] in selection["obligations"] for module in modules)
    assert all(module["stage_node"] in selection["stages"] for module in modules)


def test_payload_semantic_repair_keeps_frozen_coverage_target(tmp_path):
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.ai_generation.tree_factory import propose_payload
    target, valid = _SUITES["T321"]
    study = _PlanThenPayloadStudy(MEDICINE_LINEAR4, valid)
    original = study.invoke
    messages_seen = []

    async def invoke(directory, request_id, messages, params, **kwargs):
        messages_seen.append(messages)
        study.payload = dict(valid, close_gate="none") if not study.calls else valid
        return await original(directory, request_id, messages, params, **kwargs)

    study.invoke = invoke
    task = {"id": "semantic-repair", "suite": "T321", "seed": 2024,
            "difficulty": "M", "target": target}
    payload, calls = asyncio.run(propose_payload(study, suite_spec("T321", typed=True), task, tmp_path))
    assert payload["close_gate"] == target["close_gate"]
    assert len(calls) == 2 and calls[0]["request_id"] != calls[1]["request_id"]
    assert "close_gate" in messages_seen[1][-1]["content"]


def test_runtime_agents_follow_generated_payload_not_static_probe(tmp_path):
    target, payload = _SUITES["T331"]
    payload = dict(payload, propagation_topology="chain", fanout_width=3)
    study = _PlanThenPayloadStudy(MEDICINE_FORK_JOIN, payload)
    row = _run_r3(tmp_path, study, "T331", target, MEDICINE_FORK_JOIN)
    assert row["status"] == "PASS", row
    directory = tmp_path / "candidates/R3-TEST-T331"
    pair = json.loads((directory / "PAIR.json").read_text(encoding="utf-8"))
    binding = json.loads((directory / "BUSINESS_BINDING.json").read_text(encoding="utf-8"))
    assert {grant["agent_id"] for grant in binding["role_bindings"]} == set(pair[0]["world"]["chain"])


def test_payload_repair_includes_compiler_fidelity_constraints(tmp_path):
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.ai_generation.t321_dyna_compiler import _offer_profiles
    from ioabench.v5.ai_generation.tree_factory import propose_payload
    target, valid = _SUITES["T321"]
    invalid = dict(valid, offer_profiles=_offer_profiles(3))
    study = _PlanThenPayloadStudy(MEDICINE_LINEAR4, invalid)
    original = study.invoke

    async def invoke(directory, request_id, messages, params, **kwargs):
        study.payload = dict(invalid, broker_count=3) if study.calls else invalid
        return await original(directory, request_id, messages, params, **kwargs)

    study.invoke = invoke
    task = {"id": "fidelity-repair", "suite": "T321", "seed": 2024,
            "difficulty": "M", "target": target}
    payload, calls = asyncio.run(propose_payload(study, suite_spec("T321", typed=True), task, tmp_path))
    assert payload["broker_count"] == 3
    assert len(calls) == 2


def _policy():
    from ioabench.v5.ai_generation.development import validate_policy
    return validate_policy({"version": "ioabench.v5.development-policy/1.1.0",
                            "scope": "DEVELOPMENT_AUTO_AUDITED", "provider": "aihubmix",
                            "base_url": "https://aihubmix.com/v1", "model_id": "deepseek-v4.1-flash-1017",
                            "cross_family_exclusion": False, "human_gold_prerequisite": False,
                            "formal_scientific_claims": False, "same_model_audit_independent_science": False,
                            "formal_accepted": False, "minimum_recorded_strict_replays": 6,
                            "near_duplicate_threshold": 0.9, "audit_efforts": ["high", "max"]})


def _run_r3(tmp_path, study, suite, target, plan, *, assertions=None, seed=2024):
    from ioabench.v5.ai_generation.tree_factory import run_task
    index = json.loads(SEALED_INDEX.read_text(encoding="utf-8"))
    references = [row["features"] for row in index["records"]]
    if assertions is None:
        assertions = {"T321": ["T321-A1"], "T331": ["T331-A1"], "T362": ["T362-A1"]}[suite]
    task = {"id": f"R3-TEST-{suite}", "suite": suite, "seed": seed, "difficulty": "M",
            "effort": "high", "target": target, "assertions": assertions,
            "industry": plan["industry"]}
    return asyncio.run(run_task(study, task, index, references, workspace=ROOT,
                                policy=_policy(), out=tmp_path, route="compositional_r3"))


_SUITES = {
    "T321": ({"close_gate": "profile_verified"},
             {"item_labels": ["account register", "audit appendix"], "item_count": 2,
              "required_version": 4, "conflicting_claim": True, "close_gate": "profile_verified"}),
    "T331": ({"rebroadcast_timing": "after_propagation"},
             {"organization": "Northlake Operations", "fanout_width": 2,
              "field_name": "stock_on_hand", "rebroadcast_timing": "after_propagation"}),
    "T362": ({"evidence_access": "record_query", "evidence_flow": "moderator_hub",
              "evidence_release": "after_alert", "source_release": "per_owner_turn"},
             {"evidence_access": "record_query", "evidence_flow": "moderator_hub",
              "evidence_release": "after_alert", "source_release": "per_owner_turn"}),
}


@pytest.mark.parametrize("broken", [False, True, "missing"])
def test_empty_assertions_still_enforce_real_business_witnesses(tmp_path, monkeypatch, broken):
    from ioabench.v5.ai_generation import compiler_capabilities
    witness = compiler_capabilities.business_witnesses
    seen = []

    def inspect_runs(binding, runs):
        seen.extend(runs)
        assert {run["arm"] for run in runs} == {"CONTROL", "RISK"}
        assert all(run["trace"].actions for run in runs)
        if broken == "missing":
            return []
        if broken:
            run = next(run for run in runs if run["arm"] == "RISK" and run["policy"] == "witness")
            action = next(action for action in run["trace"].actions
                          if (action.result or {}).get("stage_id") == "s1")
            object.__setattr__(action, "status", "error")
        return witness(binding, runs)

    monkeypatch.setattr(compiler_capabilities, "business_witnesses", inspect_runs)
    target, payload = _SUITES["T321"]
    row = _run_r3(tmp_path, _PlanThenPayloadStudy(MEDICINE_LINEAR4, payload),
                  "T321", target, MEDICINE_LINEAR4, assertions=[])
    directory = tmp_path / "candidates" / "R3-TEST-T321"
    assert seen, "assertions=[] silently bypassed business witnesses"
    claims = [json.loads(line) for line in
              (directory / "BUSINESS_WITNESSES.jsonl").read_text(encoding="utf-8").splitlines()]
    assert bool(claims) == (broken != "missing")
    if broken:
        assert row["status"] == "REJECTED", row
        assert row["failed_stage"] == "BUSINESS_EXECUTION_FIDELITY"
        assert row["engineering_status"] != "DEV_ENGINEERING_VALID"
    else:
        assert row["status"] == "PASS", row
        assert all(claim["status"] == "WITNESSED" for claim in claims)


@pytest.mark.parametrize("seed,taken", [(7, True), (14, False)])
def test_real_conditional_branch_is_executed_or_explicitly_unexercised(tmp_path, seed, taken):
    target, payload = _SUITES["T321"]
    row = _run_r3(tmp_path, _PlanThenPayloadStudy(MEDICINE_CONDITIONAL, payload),
                  "T321", target, MEDICINE_CONDITIONAL, assertions=[], seed=seed)
    assert row["status"] == "PASS", row
    directory = tmp_path / "candidates/R3-TEST-T321"
    claims = [json.loads(line) for line in (directory / "BUSINESS_WITNESSES.jsonl").read_text().splitlines()]
    conditional = [claim for claim in claims if claim["stage_id"] in {"s3", "s4"}]
    assert {claim["status"] for claim in conditional} == {"WITNESSED" if taken else "NOT_EXERCISED"}
    traces = json.loads((directory / "BUSINESS_REFERENCE_TRACES.json").read_text())
    for trace in (trace for trace in traces if trace["policy"] == "witness"):
        stages = {(action.get("result") or {}).get("stage_id") for action in trace["actions"]
                  if action["status"] == "ok"}
        assert ({"s3", "s4"} <= stages) == taken


@pytest.mark.parametrize("suite,plan", [("T321", MEDICINE_LINEAR4),
                                        ("T321", MEDICINE_FORK_JOIN),
                                        ("T331", MEDICINE_FORK_JOIN),
                                        ("T331", FINANCE_FORK_JOIN),
                                        ("T362", MEDICINE_LINEAR4)])
def test_compositional_r3_full_chain_executes_model_proposed_dags(tmp_path, suite, plan):
    target, payload = _SUITES[suite]
    study = _PlanThenPayloadStudy(plan, payload)
    row = _run_r3(tmp_path, study, suite, target, plan)
    directory = tmp_path / "candidates" / f"R3-TEST-{suite}"
    assert row["status"] == "PASS", row
    trace = [json.loads(line)["step"] for line in
             (directory / "IR_CONSUMPTION_TRACE.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "workflow_plan.proposed" in trace and "workflow_plan.compiled" in trace
    assert "blueprint_from_ir" in trace
    compiled = json.loads((directory / "COMPILED_WORKFLOW.json").read_text(encoding="utf-8"))
    assert len(compiled["plan"]) == len(plan["stages"])
    witnesses = [json.loads(line) for line in
                 (directory / "BUSINESS_WITNESSES.jsonl").read_text(encoding="utf-8").splitlines()]
    assert witnesses, "business witnesses missing"
    assert all(item["status"] == "WITNESSED" for item in witnesses), witnesses
    # the runtime actually ran every planned stage (join barriers included)
    reference = json.loads((directory / "REFERENCE_RESULTS.json").read_text(encoding="utf-8"))
    assert all(result["status"] == "COMPLETED" for result in reference)
    # family novelty vs the frozen R1/R2 universe
    frozen = json.loads((ROOT / "artifacts/v5/data_factory/tree_factory_r3/tf-r3-20261025-r1"
                         / "FROZEN_REFERENCES.json").read_text(encoding="utf-8"))
    legacy_hashes = set(frozen["r2_sealed"]["distinct_workflow_hashes"])
    if len(plan["stages"]) >= 4:
        assert compiled["canonical_workflow_hash"] not in legacy_hashes


def test_compositional_r3_rejects_repeatedly_invalid_plans_before_the_compiler(tmp_path):
    plan_missing_edge = {"version": PLAN_VERSION, "industry": "industry.medicine_supply",
                         "goal": "g", "stages": MEDICINE_LINEAR3["stages"],
                         "edges": [{"from": "s1", "to": "s2", "type": "evidence"}]}
    target, payload = _SUITES["T321"]
    study = _PlanThenPayloadStudy(plan_missing_edge, payload,
                                  plans=[plan_missing_edge, plan_missing_edge])
    row = _run_r3(tmp_path, study, "T321", target, plan_missing_edge)
    assert row["status"] == "REJECTED"
    assert row["failed_stage"] == "WORKFLOW_PLAN_INVALID"
    directory = tmp_path / "candidates" / "R3-TEST-T321"
    trace_path = directory / "IR_CONSUMPTION_TRACE.jsonl"
    trace = ([json.loads(line)["step"] for line in
              trace_path.read_text(encoding="utf-8").splitlines()]
             if trace_path.exists() else [])
    assert "blueprint_from_ir" not in trace                         # never reached the compiler
    assert len(study.calls) == 3                                  # payload, plan, one repair


def test_compositional_r3_repairs_an_invalid_plan_on_a_new_request_id(tmp_path):
    broken = {"version": PLAN_VERSION, "industry": "industry.medicine_supply",
              "goal": "g", "stages": MEDICINE_LINEAR3["stages"],
              "edges": [{"from": "s1", "to": "s2", "type": "evidence"}]}
    target, payload = _SUITES["T321"]
    study = _PlanThenPayloadStudy(broken, payload, plans=[broken, MEDICINE_LINEAR3])
    row = _run_r3(tmp_path, study, "T321", target, broken)
    assert row["status"] == "PASS", row
    assert [call for call in study.calls if call.startswith("wf-plan")] == \
        [study.calls[1], study.calls[1] + "-repair-1"]


def test_reuses_real_proposal_without_regenerating_or_mutating_source(tmp_path):
    from ioabench.v5.ai_generation.tree_factory import run_task
    target, payload = _SUITES["T321"]
    study = _PlanThenPayloadStudy(MEDICINE_LINEAR4, payload)
    original = _run_r3(tmp_path, study, "T321", target, MEDICINE_LINEAR4, assertions=[])
    assert original["status"] == "PASS", original
    source = tmp_path / "candidates/R3-TEST-T321"
    before = {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    task = dict(original["task"], id="R3-TEST-T321-repaired")
    index = json.loads(SEALED_INDEX.read_text(encoding="utf-8"))
    count = len(study.calls)
    repaired = asyncio.run(run_task(
        study, task, index, [row["features"] for row in index["records"]], workspace=tmp_path,
        policy=_policy(), out=tmp_path, route="compositional_r3", proposal_source=source))
    assert repaired["status"] == "PASS", repaired
    assert len(study.calls) == count
    assert before == {path.name: path.read_bytes() for path in source.iterdir() if path.is_file()}
    assert (tmp_path / "candidates/R3-TEST-T321-repaired/PROPOSAL_REUSE.json").exists()


# ---------------------------------------------------------------------------
# cross-agent joins re-activate via bounded wake-ups (T331 delivery accounting)
# ---------------------------------------------------------------------------
def test_business_delivery_expectation_tracks_completed_stages():
    """Handoff expectations derive from completed stages: a naive run (no
    business activity) expects briefings only; the completed fork/join run
        expects one handoff per cross-agent dependency, including the join's
        completion before the commit (s4->s5 b1)."""
    from collections import Counter
    from ioabench.v5.dynamic.business_tools import expected_duty_deliveries
    binding, errors = _compile(MEDICINE_FORK_JOIN, "T331", ("node_a", "node_b1", "node_b2"))
    assert errors == []
    world = {"business_binding": binding.world_view()}
    naive_trace = _Trace([], [])
    naive_trace.final_state = {}
    assert expected_duty_deliveries(world, naive_trace) == \
        Counter({"node_a": 1, "node_b1": 1, "node_b2": 1})
    done_trace = _Trace([], [])
    done_trace.final_state = {"workflow_stages": {
        step["stage_id"]: {"receipt": {"receipt_id": "x"}}
        for step in binding.plan}}
    assert expected_duty_deliveries(world, done_trace) == \
        Counter({"node_a": 3, "node_b1": 3, "node_b2": 2})
    # the exact per-agent prediction is proven against real episodes by the
    # full-chain tests (T331 execution_fidelity counts message_delivered)


def test_authorized_handoffs_deliver_cross_agent_receipts_and_wake_consumers():
    from ioabench.v5.core.engine import EnvContext, ToolContext
    from ioabench.v5.core.policy import attachment_of
    from ioabench.v5.dynamic.business_tools import business_tools, reactivate_business
    binding, _ = _compile(MEDICINE_FORK_JOIN, "T331", ("node_a", "node_b1", "node_b2"))
    world = {"business_binding": binding.world_view()}
    env = EnvContext(world=world, state={},
                     inboxes={agent: ["Business duty briefing for this unit."]
                              for agent in ("node_a", "node_b1", "node_b2")})
    tools = business_tools(world)

    def ctx(actor):
        return ToolContext(actor, env)

    # node_a completes s1; both cross-agent consumers receive exactly the receipt
    # they are authorized to cite
    tools["lookup_stock"].handler(ctx("node_a"), {"lot_id": "LOT-2201"})
    env.inboxes["node_a"].clear()
    handoffs_b1 = [attachment_of(text) for text in list(env.inboxes["node_b1"])]
    assert any(isinstance(doc, dict) and doc.get("business_receipt", {}).get("stage_id") == "s1"
               for doc in handoffs_b1)
    assert not reactivate_business(env)                     # handoffs already woke consumers
    r2 = tools["verify_lot"].handler(ctx("node_b1"),
                                     {"lot_id": "LOT-2201",
                                      "receipt_id": env.state["workflow_stages"]["s1"]["receipt_id"]})
    env.inboxes["node_b1"].clear()
    tools["crosscheck_lot"].handler(ctx("node_b2"),
                                    {"lot_id": "LOT-2201",
                                     "receipt_id": env.state["workflow_stages"]["s1"]["receipt_id"]})
    env.inboxes["node_b2"].clear()
    assert r2["stage_id"] == "s2"
    # node_a now holds both join-branch receipts via authorized handoffs
    docs_a = [attachment_of(text) for text in list(env.inboxes["node_a"])]
    assert {doc.get("business_receipt", {}).get("stage_id") for doc in docs_a
            if isinstance(doc, dict)} >= {"s2", "s3"}
    review = tools["review_restock"].handler(ctx("node_a"), {
        "verification_ref": next(doc["business_receipt"]["receipt_id"] for doc in docs_a
                                 if doc.get("business_receipt", {}).get("stage_id") == "s2"),
        "crosscheck_ref": next(doc["business_receipt"]["receipt_id"] for doc in docs_a
                               if doc.get("business_receipt", {}).get("stage_id") == "s3")})
    assert review["stage_id"] == "s4"
