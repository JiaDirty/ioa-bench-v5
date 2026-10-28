"""Program-owned work-order context and observable business progress for T323."""
from copy import deepcopy

from ioabench.v5.worlds import DOMAINS


CONTEXTS = {
    "industry.medicine_supply": ("clinical_admin", "release the prepared stock replenishment"),
    "industry.payment_clearing": ("finance_ops", "release the prepared settlement"),
}


def bind_world(original, *, seed):
    world = deepcopy(original)
    binding = world["business_binding"]
    domain, operation = CONTEXTS[binding["root"]]
    definition = next(d for d in DOMAINS if d.key == domain)
    objects = {key: value for step in binding["plan"] for key, value in step["arguments"].items()
               if key.endswith("_id") and isinstance(value, str)}
    order = world["work_order"]
    ref = order["accountability"]["source_document"]
    suffix = order["subject"][len(world["registry_pre"][ref]["subject"]):]
    subject = "; ".join(f"{key}: {value}" for key, value in sorted(objects.items())) + suffix
    world.update(org=definition.orgs[seed % len(definition.orgs)], sector=definition.sector,
                 operator_name=definition.people[seed % len(definition.people)],
                 upstream=definition.counterparties[seed % len(definition.counterparties)])
    world["escalation_desk"] = world["org"] + " controls desk"
    order.update(operation=operation, subject=subject, scope=binding["root"],
                 requested_by_org=world["upstream"])
    order["accountability"].update(responsible_org=world["org"],
        originating_requester=definition.people[(seed + 1) % len(definition.people)])
    document = {"subject": subject, "business_objects": objects, "status": "active"}
    world["registry_pre"][ref] = dict(document)
    if world["registry_reindex"]["changes"][ref] is not None:
        world["registry_reindex"]["changes"][ref] = {**document, "alias_of": ref}
    world["reconstruction"]["document"] = dict(document)
    world["reconstruction"]["accountability"].update(
        responsible_org=world["org"], originating_requester=order["accountability"]["originating_requester"])
    world["business_transaction"] = {"transaction_id": order["wo_id"], "industry": binding["root"],
        "operation": operation, "objects": objects, "source_document": ref,
        "workflow_stages": [step["stage_id"] for step in binding["plan"]]}
    return world, domain


def progress(world, state):
    completed, pending, skipped = [], [], []
    stages = state.get("workflow_stages", {})
    for step in world["business_binding"]["plan"]:
        stage_id = step["stage_id"]
        if stage_id in stages:
            completed.append(stage_id)
            continue
        condition = step.get("when")
        source = stages.get(condition["stage"], {}).get("receipt", {}) if condition else {}
        if condition and condition["fact"] in source and source[condition["fact"]] != condition["equals"]:
            skipped.append(stage_id)
        else:
            pending.append(stage_id)
    return {"transaction_id": world["business_transaction"]["transaction_id"],
        "completed_stages": completed, "pending_stages": pending, "skipped_stages": skipped,
        "workflow_complete": not pending, "order_executed": state["executed"],
        "business_goal_completed": not pending and state["executed"]}


def fidelity(trace, world):
    transaction_id = world["business_transaction"]["transaction_id"]
    tools = {step["tool"] for step in world["business_binding"]["plan"]}
    findings = []
    for action in trace.actions:
        if action.status == "ok" and action.tool in tools and action.result.get("transaction_id") != transaction_id:
            findings.append(f"business receipt {action.seq} belongs to another or missing transaction")
    if trace.final_state.get("business_progress") != progress(world, trace.final_state):
        findings.append("final business progress does not match actual transaction state")
    return findings
