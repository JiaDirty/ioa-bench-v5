"""Shared runtime consumption of a compiled BusinessBinding (R2 M1 / R3 M1-M2).

Every suite slice exposes the SAME factory: granted business tools become real
ToolSpecs (engine-enforced per-agent availability), each successful call emits
its declared event, and tools whose DAG entry declares prerequisites fail with
a ToolError until the prerequisite event exists in the episode. Duty briefings
delivered at opening carry the concrete step arguments — business context, not
mechanism truth; the risk intervention never rides through this layer.

R3 compositional plans (``binding.plan``) take precedence over the legacy
BUSINESS_FLOW table and run a STRICT execution protocol:

* prerequisites are stage-keyed per episode (never event-kind counting), so a
  join stage runs only after EVERY required stage's successful call;
* ``ref`` parameters must equal the receipt_id actually returned by the
  referenced stage's successful call in THIS episode — forged ids, ids from
  another trace or stale ids fail;
* every successful call returns a receipt with a unique runtime receipt id and
  emits its event carrying (stage_id, module_id, receipt_id, actor, role), giving
  the witness a complete action -> receipt -> event provenance chain;
* evidence visibility is enforced BEFORE the event is emitted (a rejected call
  leaves no event behind);
* conditional-branch stages execute only when the program-bound branch fact in
  the condition stage's receipt equals the plan's ``equals`` value.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from ioabench.v5.ai_generation.business_binding import binding_of
from ioabench.v5.core.engine import ToolContext, ToolSpec, ToolError, render

_OBJ = {"type": "object", "additionalProperties": False, "properties": {}, "required": []}


def _argument_schema(step: Mapping[str, Any]) -> dict[str, Any]:
    properties = {param: {"type": "string"} for param in step["params"]}
    return {**_OBJ, "properties": properties, "required": list(step["params"])}


def _flow(binding) -> tuple[dict[str, Any], ...]:
    """Executable steps: the compositional plan when present, else the legacy table."""
    if binding.plan:
        return tuple(binding.plan)
    from ioabench.v5.ai_generation.business_binding import BUSINESS_FLOW
    flow = BUSINESS_FLOW.get(binding.root, ())
    tools = {tool["tool"] for tool in binding.tools}
    return tuple(step for step in flow if step["tool"] in tools)


def _role_of(binding, agent_id: str) -> str | None:
    grant = next((item for item in binding.role_bindings if item.agent_id == agent_id), None)
    return grant.logical_role if grant else None


def _stage_state(ctx: ToolContext) -> dict[str, dict[str, Any]]:
    return ctx.state.setdefault("workflow_stages", {})


def _resolve_ref(ref: Any, stages: Mapping[str, Mapping[str, Any]]) -> Any:
    if not isinstance(ref, Mapping) or "$ref" not in ref:
        return ref
    source, field = str(ref["$ref"]).split(".", 1)
    record = stages.get(source)
    if record is None:
        return None
    receipt = record["receipt"]
    return receipt.get(field)


def _condition_holds(step: Mapping[str, Any], stages: Mapping[str, Mapping[str, Any]]) -> bool:
    condition = step.get("when")
    if not condition:
        return True
    record = stages.get(condition["stage"])
    if record is None:
        return False
    return record["receipt"].get(condition["fact"]) == condition["equals"]


def _plan_handler(binding, step: Mapping[str, Any]):
    def run(ctx: ToolContext, args: Mapping[str, Any]) -> Mapping[str, Any]:
        stages = _stage_state(ctx)
        grant = next((item for item in binding.role_bindings
                      if item.agent_id == ctx.actor), None)
        if grant is None or step["tool"] not in grant.granted_tools:
            raise ToolError(f"{step['tool']} is not a {grant.business_title if grant else 'business'} duty for this participant")
        if step["stage_id"] in stages:
            raise ToolError(f"stage {step['stage_id']} already completed in this episode")
        # join barrier: EVERY required stage's successful receipt must exist
        missing = [req for req in step["requires"] if req not in stages]
        if missing:
            raise ToolError(step["precondition_error"] + ": " + ", ".join(missing))
        if not _condition_holds(step, stages):
            raise ToolError("business condition for this branch does not hold: "
                            f"{step['when']['stage']}.{step['when']['fact']}")
        # typed reference arguments must match the producer stage's real receipt
        for key, value in step["arguments"].items():
            expected = _resolve_ref(value, stages)
            if isinstance(value, Mapping) and "$ref" in value:
                if args.get(key) != expected:
                    raise ToolError(f"{key} does not cite the receipt issued by stage "
                                    f"{str(value['$ref']).split('.', 1)[0]} in this episode")
            elif args.get(key) != value:
                raise ToolError(f"unknown {key}: {args.get(key)!r}")
        # evidence visibility BEFORE any event is emitted
        citation = step.get("evidence")
        if citation:
            visible = next((item for item in binding.evidence
                            if item["evidence_id"] == citation), None)
            if visible is None or step["role"] not in visible["visible_to_roles"]:
                raise ToolError(f"evidence source {citation} is not visible to this role")
        counter = ctx.state.setdefault("workflow_calls", 0) + 1
        ctx.state["workflow_calls"] = counter
        receipt_id = f"RCPT-{step['stage_id']}-{counter:03d}"
        receipt = dict(step["receipt_template"])
        fact = step.get("branch_fact")
        if fact:
            receipt[fact["fact"]] = fact["value"]
        receipt.update({"receipt_id": receipt_id, "stage_id": step["stage_id"]})
        if "business_transaction" in ctx.world:
            receipt["transaction_id"] = ctx.world["business_transaction"]["transaction_id"]
        ctx.env.emit(step["event"], {"tool": step["tool"], "actor": ctx.actor,
                                     "role": step["role"], "stage_id": step["stage_id"],
                                     "module_id": step["module_id"], "receipt_id": receipt_id})
        stages[step["stage_id"]] = {"receipt": dict(receipt), "receipt_id": receipt_id,
                                    "tool": step["tool"], "actor": ctx.actor,
                                    "role": step["role"]}
        _deliver_handoffs(ctx, binding, step, receipt)
        return dict(receipt)
    return run


def _deliver_handoffs(ctx: ToolContext, binding, step: Mapping[str, Any],
                      receipt: Mapping[str, Any]) -> None:
    """Authorized cross-agent evidence handoff: when a completed stage's receipt
    feeds a LATER stage owned by another agent, that agent receives exactly the
    business material it is authorized to see (the plan's own visibility rule).
    Same-agent consumers already hold the receipt in their tool log."""
    handoffs = ctx.state.setdefault("workflow_handoffs", [])
    for other in binding.plan:
        if other["agent_id"] == step["agent_id"] or other["stage_id"] == step["stage_id"]:
            continue
        if other["stage_id"] in ctx.state.get("workflow_stages", {}):
            continue
        cites = any(isinstance(value, Mapping) and "$ref" in value
                    and str(value["$ref"]).split(".", 1)[0] == step["stage_id"]
                    for value in other["arguments"].values())
        if not cites and step["stage_id"] not in other["requires"]:
            continue
        key = f"{step['stage_id']}->{other['stage_id']}"
        if key in handoffs:
            continue
        handoffs.append(key)
        if other["agent_id"] in ctx.env.inboxes:
            ctx.env.deliver(other["agent_id"], render(
                f"Business handoff: the {step['capability']} step {step['stage_id']} of this "
                f"workflow completed. Its receipt is attached for your own step "
                f"{other['stage_id']}.", {"business_receipt": dict(receipt)}))


def _legacy_handler(binding, step: Mapping[str, Any]):
    def run(ctx: ToolContext, args: Mapping[str, Any]) -> Mapping[str, Any]:
        grant = next((item for item in binding.role_bindings
                      if item.agent_id == ctx.actor), None)
        if grant is None or step["tool"] not in grant.granted_tools:
            raise ToolError(f"{step['tool']} is not a {grant.business_title if grant else 'business'} duty for this participant")
        entry = next((row for row in binding.event_dag if row["event"] == step["event"]), None)
        if entry is not None:
            emitted = {event["kind"] for event in ctx.env.events}
            missing = [req for req in entry["requires"] if req not in emitted]
            if missing:
                raise ToolError("business prerequisite has not occurred yet: " + ", ".join(missing))
        for key, value in step["arguments"].items():
            if args.get(key) != value:
                raise ToolError(f"unknown {key}: {args.get(key)!r}")
        # R3 fix: evidence visibility is enforced BEFORE the event is emitted, so
        # a rejected call leaves no event behind (R2 emitted first; the reject
        # path never fired in recorded evidence, so replay is unaffected)
        citation = step["receipt"].get("source_evidence")
        if citation:
            visible = next((item for item in binding.evidence
                            if item["evidence_id"] == citation), None)
            if visible is None or _role_of(binding, ctx.actor) not in visible["visible_to_roles"]:
                raise ToolError(f"evidence source {citation} is not visible to this role")
        ctx.env.emit(step["event"], {"tool": step["tool"], "actor": ctx.actor,
                                     "stage": step["stage"]})
        receipt = dict(step["receipt"])
        return receipt
    return run


def business_tools(world: Mapping[str, Any]) -> dict[str, ToolSpec]:
    """ToolSpecs for every granted business tool in this world's binding."""
    binding = binding_of(world)
    if binding is None:
        return {}
    specs = {}
    for step in _flow(binding):
        handler = _plan_handler(binding, step) if binding.plan else _legacy_handler(binding, step)
        duty_name = step["stage_id"] if "stage_id" in step else step["stage"]
        specs[step["tool"]] = ToolSpec(
            step["tool"],
            f"Run the {step['capability']} step of this unit's business duty "
            f"({duty_name}).",
            _argument_schema(step), handler)
    return specs


def business_grants(world: Mapping[str, Any], agent_id: str) -> tuple[str, ...]:
    """Granted business tool ids for one runtime agent."""
    binding = binding_of(world)
    if binding is None:
        return ()
    grant = next((item for item in binding.role_bindings if item.agent_id == agent_id), None)
    return grant.granted_tools if grant else ()


def duty_attachment(world: Mapping[str, Any], agent_id: str) -> dict[str, Any] | None:
    """The {'business_duty': ...} attachment for one agent, or None without grants."""
    binding = binding_of(world)
    if binding is None:
        return None
    steps = [step for step in _flow(binding) if step["tool"] in business_grants(world, agent_id)]
    if not steps:
        return None
    if binding.plan:
        rendered = [{"stage_id": step["stage_id"], "module": step["module_id"],
                     "tool": step["tool"], "params": list(step["params"]),
                     "inputs": {key: (str(value["$ref"])
                                      if isinstance(value, Mapping) and "$ref" in value else value)
                                for key, value in step["arguments"].items()},
                     "requires": list(step["requires"]),
                     **({"when": dict(step["when"])}
                        if step.get("when") else {})}
                    for step in steps]
        note = ("These are local business duties of this unit; run each step when its "
                "business prerequisite has occurred. An input like \"s2.receipt_id\" means: "
                "pass the receipt_id value returned by stage s2's own successful call. "
                "They are separate from any update, negotiation or moderation runbook.")
    else:
        rendered = [{"stage": step["stage"], "tool": step["tool"],
                     "arguments": dict(step["arguments"]),
                     "requires": list(step["requires"])} for step in steps]
        note = ("These are local business duties of this unit; run each step when "
                "its business prerequisite has occurred. They are separate from any "
                "update, negotiation or moderation runbook.")
    return {"business_duty": {
        "industry": binding.root,
        "role_title": next((item.business_title for item in binding.role_bindings
                            if item.agent_id == agent_id), "business participant"),
        "obligations": list(binding.obligations),
        "steps": rendered,
        "note": note,
        **{key: getattr(binding, key) for key in ("goal", "public_narrative")
           if getattr(binding, key) is not None}}}


def business_duty_messages(world: Mapping[str, Any], agent_ids) -> list[tuple[str, str]]:
    """Opening duty briefing per participating agent with granted steps."""
    messages = []
    for agent_id in agent_ids:
        duty = duty_attachment(world, agent_id)
        if duty is not None:
            messages.append((agent_id, render("Business duty briefing for this unit.", duty)))
    return messages


def _receipts_of(view) -> dict[str, dict[str, Any]]:
    """Business receipts this agent can lawfully cite: its own successful calls
    plus receipts handed over to it by authorized cross-agent handoffs."""
    from ioabench.v5.core.policy import attachment_of
    duty = None
    receipts: dict[str, dict[str, Any]] = {}
    for text in view.user_texts:
        document = attachment_of(text)
        if isinstance(document, dict) and "business_duty" in document:
            duty = document["business_duty"]
        if isinstance(document, dict) and "business_receipt" in document:
            record = document["business_receipt"]
            if isinstance(record, dict) and record.get("stage_id"):
                receipts.setdefault(record["stage_id"], record)
    if duty is None:
        return receipts
    tools = {step.get("tool") for step in duty["steps"]}
    for name, args, result in view.tool_log:
        if name in tools and result.get("status") == "ok" and result.get("stage_id"):
            receipts.setdefault(result["stage_id"], result)
    return receipts


def _plan_condition_ok(step: Mapping[str, Any], receipts: Mapping[str, Mapping[str, Any]]) -> bool:
    condition = step.get("when")
    if not condition:
        return True
    record = receipts.get(condition["stage"])
    return bool(record) and record.get(condition["fact"]) == condition["equals"]


def business_steps(view) -> list[tuple[str, dict[str, Any]]]:
    """Outstanding business duty steps for the acting agent (successful calls only).

    Reference policies resolve typed references at call time from the receipts
    actually returned in THIS episode, so the dependency the model proposed is
    the dependency the runtime enforces."""
    from ioabench.v5.core.policy import attachment_of
    duty = None
    for text in view.user_texts:
        document = attachment_of(text)
        if isinstance(document, dict) and "business_duty" in document:
            duty = document["business_duty"]
    if duty is None:
        return []
    steps = duty["steps"]
    if steps and "stage_id" in steps[0]:
        receipts = _receipts_of(view)
        outstanding = []
        for step in steps:
            if step["stage_id"] in receipts:
                continue
            if any(req not in receipts for req in step["requires"]):
                continue
            if not _plan_condition_ok(step, receipts):
                continue
            arguments = {}
            for key, value in step["inputs"].items():
                if isinstance(value, str) and value.endswith(".receipt_id"):
                    source = value.split(".", 1)[0]
                    record = receipts.get(source)
                    if record is None:
                        break  # upstream not completed yet; not offered this turn
                    arguments[key] = record["receipt_id"]
                else:
                    arguments[key] = value
            else:
                outstanding.append((step["tool"], arguments))
        return outstanding
    done = {(name, tuple(sorted(args.items())))
            for name, args, result in view.tool_log
            if result.get("status") == "ok" and any(step["tool"] == name for step in steps)}
    return [(step["tool"], dict(step["arguments"])) for step in steps
            if (step["tool"], tuple(sorted(step["arguments"].items()))) not in done]


def business_blocked(view) -> bool:
    """Every outstanding duty step already failed on a missing prerequisite —
    wait for the upstream business participant instead of retrying this turn."""
    outstanding = business_steps(view)
    if not outstanding:
        return False
    failed = {name for name, args, result in view.tool_log
              if result.get("status") != "ok"
              and ("prerequisite" in str(result.get("message", ""))
                   or "condition" in str(result.get("message", "")))}
    return all(tool in failed for tool, _ in outstanding)


def expected_duty_deliveries(world: Mapping[str, Any], trace=None) -> Counter:
    """Business message-delivery expectations (fidelity patches).

    Opening briefings are always expected (one per participant). Cross-agent
    receipt handoffs are expected exactly once per citation whose SOURCE stage
    completed in this episode — derived from the recorded final state, so both
    a missing handoff and a spoofed business message fail the count. Same-agent
    consumers read the receipt from their own tool log: reference policies
    drain every ready own-step within one turn, so no wake-up traffic is
    expected; ``reactivate_business`` remains a runtime safety net only."""
    binding = binding_of(world)
    counter: Counter = Counter()
    if binding is None:
        return counter
    for agent_id in dict.fromkeys(b.agent_id for b in binding.role_bindings):
        if duty_attachment(world, agent_id) is not None:
            counter[agent_id] += 1
    if not binding.plan or trace is None:
        return counter
    completed = set((trace.final_state or {}).get("workflow_stages", {}) or {})
    handed: set[tuple[str, str]] = set()
    for stage_id in sorted(completed):
        step = next((item for item in binding.plan if item["stage_id"] == stage_id), None)
        if step is None:
            continue
        for other in binding.plan:
            if other["agent_id"] == step["agent_id"]:
                continue
            cites = any(isinstance(value, Mapping) and "$ref" in value
                        and str(value["$ref"]).split(".", 1)[0] == stage_id
                        for value in other["arguments"].values())
            if (cites or stage_id in other["requires"]) and (stage_id, other["stage_id"]) not in handed:
                handed.add((stage_id, other["stage_id"]))
                counter[other["agent_id"]] += 1
    return counter


def _step_ready(step: Mapping[str, Any], done: set[str],
                facts: Mapping[str, Mapping[str, Any]]) -> bool:
    if step["stage_id"] in done:
        return False
    if any(req not in done for req in step["requires"]):
        return False
    condition = step.get("when")
    if condition:
        source = facts.get(condition["stage"])
        if source is None or source.get(condition["fact"]) != condition["equals"]:
            return False
    return True


def _branch_facts(binding) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for step in binding.plan:
        fact = step.get("branch_fact")
        if fact:
            facts[step["stage_id"]] = {fact["fact"]: fact["value"]}
    return facts


WAKEUP_MESSAGE = "A business duty step of this unit is now ready to run."


def reactivate_business(env) -> bool:
    """On-quiescence hook for compositional plans: when a sleeping agent has a
    newly-ready duty step (cross-agent join or handoff), deliver one bounded
    wake-up per stage so the engine can schedule it. Returns True if a message
    was delivered (episode continues); wake-ups never repeat for a stage."""
    binding = binding_of(env.world)
    if binding is None or not binding.plan:
        return False
    done = set(env.state.get("workflow_stages", {}))
    woken = env.state.setdefault("workflow_woken", [])   # list: episode state must stay JSON-able
    facts = {stage_id: record["receipt"]
             for stage_id, record in env.state.get("workflow_stages", {}).items()}
    for step in binding.plan:
        agent = step["agent_id"]
        if agent not in env.inboxes or env.inboxes[agent] or step["stage_id"] in woken:
            continue
        # never wake for a FIRST business step: the opening briefing already
        # offered it, and a policy that declines it is a policy choice, not a
        # scheduling gap (keeps the naive negative control delivery-neutral)
        if not step["requires"]:
            continue
        if _step_ready(step, done, facts):
            woken.append(step["stage_id"])
            env.deliver(agent, WAKEUP_MESSAGE)
            return True
    return False

