"""Mechanism evidence must be specific, observed and earlier than the decision."""
import asyncio
from copy import deepcopy
import json

import pytest

from ioabench.v5.ai_generation.compiler_capabilities import (
    ASSERTION_DEPENDENCIES, PILOT_FACTORS, SUITE_MECHANISM_EVENTS, execution_witnesses,
)
from ioabench.v5.core.engine import run_episode
from ioabench.v5.dynamic import t311_slice, t351_slice
from test_t311_business_composition import PROFILE, compiled_pair as t311_pair
from test_t351_business_composition import compiled_pair as t351_pair


def make_run(suite, arm="RISK", access=None):
    if suite == "T311":
        _, pair = t311_pair("industry.medicine_supply", "fork_join", access or "requested_document")
        scenario, policy = t311_slice.T311DynamicScenario(), t311_slice.policies()["witness"]
    else:
        _, pair = t351_pair("industry.medicine_supply", "fork_join", access or "queued_history_reply")
        scenario, policy = t351_slice.T351DynamicScenario(), t351_slice.policies()["witness"]
    case = next(c for c in pair if c.arm == arm)
    trace = asyncio.run(run_episode(case, scenario, policy, PROFILE, parameters={}))
    return {"arm": arm, "policy": "witness", "trace": trace, "world": case.world}


def status(assertion, run):
    return execution_witnesses([assertion], [run])[0]["status"]


@pytest.mark.parametrize("suite,assertion", [("T311", "T311-A1"), ("T351", "T351-A1")])
@pytest.mark.parametrize("arm", ["CONTROL", "RISK"])
def test_mechanism_is_registered_and_witnessed_in_both_arms(suite, assertion, arm):
    assert suite in PILOT_FACTORS and suite in SUITE_MECHANISM_EVENTS
    assert assertion in ASSERTION_DEPENDENCIES
    assert status(assertion, make_run(suite, arm)) == "WITNESSED"


@pytest.mark.parametrize("mutation", ["no_assignment", "wrong_provider", "wrong_actor", "wrong_reference", "wrong_entry", "unobserved", "lookup_after_assignment"])
def test_t311_rejects_unproven_issuer_confirmation(mutation):
    run = make_run("T311", access="directory")
    trace = run["trace"]
    assignment = next(a for a in trace.actions if a.tool == "assign_task" and a.status == "ok")
    provider = next(p for p in run["world"]["directory"] if p["provider_id"] == assignment.arguments["provider_id"])
    ref = provider["claim"]["credential_ref"]
    lookup = next(a for a in trace.actions if a.tool == "query_issuer_register" and a.arguments["credential_ref"] == ref)
    if mutation == "no_assignment":
        assignment.status = "error"
    elif mutation == "wrong_provider":
        assignment.arguments["provider_id"] = "unknown"
    elif mutation == "wrong_actor":
        lookup.actor = "other"
    elif mutation == "wrong_reference":
        lookup.arguments["credential_ref"] = "other"
    elif mutation == "wrong_entry":
        lookup.result["entries"] = []
    elif mutation == "lookup_after_assignment":
        lookup.seq = assignment.seq + 1
    else:
        for record in trace.records:
            if any(call["function"]["name"] == "assign_task" for call in record["response"].get("tool_calls", [])):
                record["request"]["messages"] = [m for m in record["request"]["messages"]
                    if m.get("role") != "tool" or json.loads(m["content"]) != lookup.result]
    assert status("T311-A1", run) == "DESIGN_EXECUTION_FIDELITY_FAIL"


@pytest.mark.parametrize("mutation", ["no_release", "wrong_item", "missing_request", "wrong_receipt", "unobserved"])
def test_t351_rejects_unproven_screening_before_release(mutation):
    run = make_run("T351")
    trace = run["trace"]
    release = next(a for a in trace.actions if a.tool == "release" and a.status == "ok")
    item_id = release.arguments["item_id"]
    request = next(a for a in trace.actions if a.tool == "request_check" and a.arguments["item_id"] == item_id)
    receipt = next(a for a in trace.actions if a.tool == "lookup_check_history"
                   and a.arguments["item_id"] == item_id and (a.result.get("result") or {}).get("result") == "pass")
    if mutation == "no_release":
        release.status = "error"
    elif mutation == "wrong_item":
        release.arguments["item_id"] = "other"
    elif mutation == "missing_request":
        request.status = "error"
    elif mutation == "wrong_receipt":
        receipt.result["result"]["result"] = "fail"
    else:
        for record in trace.records:
            if any(call["function"]["name"] == "release" and json.loads(call["function"]["arguments"])["item_id"] == item_id
                   for call in record["response"].get("tool_calls", [])):
                record["request"]["messages"] = [m for m in record["request"]["messages"]
                    if m.get("role") != "tool" or json.loads(m["content"]) != receipt.result]
    assert status("T351-A1", run) == "DESIGN_EXECUTION_FIDELITY_FAIL"


def test_t351_queued_assertion_is_not_satisfied_by_automatic_push():
    assert status("T351-A1", make_run("T351", access="automatic_push")) == "DESIGN_EXECUTION_FIDELITY_FAIL"
