"""Turn-based multi-agent episode engine for v5 suites.

ADR-V5-000 P1/P2/P7/P9/P12. One engine executes every suite. A suite contributes a ``Scenario``:
agents, typed tools, an opening, optional scripted reactions and an evaluator-side scorer. The
engine guarantees, structurally:

* tool handlers and scripted reactions receive the case *world* and mutable *state* only — never
  the oracle, the arm or the case id;
* every observation appended to a tested agent's context passes the observation firewall;
* every provider request/response is recorded (and journaled when an AttemptJournal is active);
* every world transition lands in the causal event ledger (``core/events.py``): inbox
  deliveries and tool executions carry actor, channel, visibility, authority reference and
  state_before/state_after hashes with stable ids and parent links; legacy events keep their
  ``{seq, turn, kind, payload}`` shape, so existing consumers keep working;
* thinking/reasoning channels are persisted. Direct DeepSeek requests replay ``reasoning_content``
  with assistant messages when tools are present, as its API requires; the historical AIHubMix
  protocol keeps its no-replay behavior;
* malformed tool calls are answered with a business-level error, so interface slips do not erase
  behavior; only repeated malformed output ends the episode as ``INVALID_MODEL_OUTPUT``.
"""
from __future__ import annotations

import json
import time
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

import jsonschema

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelRequest, ModelResponse
from ioabench.runtime.scientific_io import AttemptJournal
from ioabench.v5.core.authority import AuthorityLedger
from ioabench.v5.core.case import Case
from ioabench.v5.core.clock import LogicalClock
from ioabench.v5.core.events import make_event
from ioabench.v5.core.evidence import EvidenceGraph
from ioabench.v5.core.firewall import ObservationFirewall

ENGINE_VERSION = "v5-episode-engine-1.4.2"
MAX_CONSECUTIVE_MALFORMED = 3


class ToolError(Exception):
    """Business-level failure of a tool call; reported to the calling agent as an error result."""


class InvalidModelOutput(RuntimeError):
    """The tested model produced unusable output (empty, truncated or persistently malformed)."""


class EpisodeBudgetExceeded(RuntimeError):
    """The episode hit a declared action budget."""


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    organization: str
    role: str
    system_prompt: str
    tools: tuple[str, ...]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Mapping[str, Any]
    handler: Callable[["ToolContext", Mapping[str, Any]], Mapping[str, Any]]
    decision: bool = False
    # optional executable-permission declaration: (action_token, resource_template). The
    # resource template may reference argument values ("report:{report_id}"). When set, the
    # episode's AuthorityLedger must grant the calling actor the action on the resource or the
    # call is rejected as a business-level authorization error before the handler runs.
    authority_scope: tuple[str, str] | None = None
    # optional name of the argument carrying the action's target audience/recipient; when a
    # grant is audience-constrained the engine supplies this value to the ledger check
    # (fail closed: an audience-constrained grant cannot match without it).
    audience_from_arg: str | None = None

    def schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": deepcopy(dict(self.parameters))}}


@dataclass(frozen=True)
class Budget:
    max_turns: int = 40
    max_steps_per_turn: int = 8
    max_model_calls: int = 80
    max_tool_calls: int = 160


@dataclass
class ActionRecord:
    seq: int
    turn: int
    actor: str
    tool: str
    arguments: dict[str, Any]
    status: str
    result: dict[str, Any]
    state_before_sha256: str = ""
    state_after_sha256: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "turn": self.turn, "actor": self.actor, "tool": self.tool,
                "arguments": deepcopy(self.arguments), "status": self.status, "result": deepcopy(self.result),
                "state_before_sha256": self.state_before_sha256, "state_after_sha256": self.state_after_sha256}


@dataclass
class EnvContext:
    """Runtime-side view shared by tool handlers and scripted reactions (no oracle)."""

    world: Mapping[str, Any]
    state: dict[str, Any]
    actions: list[ActionRecord] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    inboxes: dict[str, deque[str]] = field(default_factory=dict)
    turn: int = 0
    auxiliary: Mapping[str, Any] = field(default_factory=dict)
    # dynamic-world components (optional; legacy suites leave them None)
    authority: AuthorityLedger | None = None
    evidence: EvidenceGraph | None = None
    clock: LogicalClock | None = None
    # seq of the last inbox-delivery event per agent: causal parent for that agent's tool events
    _last_delivery_seq: dict[str, int] = field(default_factory=dict)

    def deliver(self, to: str, text: str) -> None:
        if to not in self.inboxes:
            raise ToolError(f"unknown recipient {to}")
        self.inboxes[to].append(text)
        self.events.append(make_event(len(self.events) + 1, self.turn, "message_enqueued",
                                      {"to": to, "chars": len(text)}, actor=None, channel="inbox",
                                      visibility="environment"))

    def emit(self, kind: str, payload: Mapping[str, Any]) -> None:
        self.events.append(make_event(len(self.events) + 1, self.turn, kind, payload))


@dataclass
class ToolContext:
    actor: str
    env: EnvContext

    @property
    def world(self) -> Mapping[str, Any]:
        return self.env.world

    @property
    def state(self) -> dict[str, Any]:
        return self.env.state


class Scenario(Protocol):
    suite_id: str
    version: str

    def agents(self, world: Mapping[str, Any]) -> Sequence[AgentSpec]: ...
    def tools(self, world: Mapping[str, Any]) -> Mapping[str, ToolSpec]: ...
    def initial_state(self, world: Mapping[str, Any]) -> dict[str, Any]: ...
    def opening(self, env: EnvContext) -> None: ...
    async def after_turn(self, env: EnvContext, agent_id: str) -> None: ...
    async def on_quiescent(self, env: EnvContext) -> bool: ...
    def budget(self, world: Mapping[str, Any]) -> Budget: ...
    def firewall_terms(self, world: Mapping[str, Any]) -> Sequence[str]: ...


@dataclass
class Trace:
    status: str
    actions: list[ActionRecord]
    events: list[dict[str, Any]]
    records: list[dict[str, Any]]
    final_state: dict[str, Any]
    agents: tuple[AgentSpec, ...]
    decision_tools: frozenset[str]
    malformed_calls: int
    error_detail: str | None = None

    def actions_of(self, tool: str, *, ok_only: bool = True) -> list[ActionRecord]:
        return [a for a in self.actions if a.tool == tool and (a.status == "ok" or not ok_only)]


class BaseScenario:
    """Defaults for optional Scenario hooks."""

    suite_id = ""
    version = ""

    async def after_turn(self, env: EnvContext, agent_id: str) -> None:
        return None

    async def on_quiescent(self, env: EnvContext) -> bool:
        return False

    def budget(self, world: Mapping[str, Any]) -> Budget:
        return Budget()

    def firewall_terms(self, world: Mapping[str, Any]) -> Sequence[str]:
        return ()

    # dynamic-world component hooks: a scenario may provide an AuthorityLedger, an
    # EvidenceGraph and a LogicalClock for its world; returning None (the default) leaves the
    # component absent and legacy behavior unchanged. ``world`` stays JSON-able — components
    # are scenario-owned runtime objects, never part of the case world.
    def authority(self, world: Mapping[str, Any]) -> AuthorityLedger | None:
        return None

    def evidence(self, world: Mapping[str, Any]) -> EvidenceGraph | None:
        return None

    def clock(self, world: Mapping[str, Any]) -> LogicalClock | None:
        return None


def render(text: str, attachments: Mapping[str, Any] | None = None) -> str:
    """Render a message as prose followed by attached records as JSON."""
    if not attachments:
        return text
    return f"{text}\n\n{json.dumps(attachments, indent=2, sort_keys=True, ensure_ascii=False)}"


async def run_episode(case: Case, scenario: Scenario, model: Any, profile: ModelProfile, *,
                      parameters: Mapping[str, Any], firewall: ObservationFirewall | None = None,
                      auxiliary: Mapping[str, Any] | None = None) -> Trace:
    world = deepcopy(dict(case.world))
    agents = tuple(scenario.agents(world))
    tools = dict(scenario.tools(world))
    budget = scenario.budget(world)
    wall = firewall or ObservationFirewall(extra_terms=scenario.firewall_terms(world))
    env = EnvContext(world=world, state=scenario.initial_state(world), auxiliary=dict(auxiliary or {}),
                     inboxes={agent.agent_id: deque() for agent in agents},
                     authority=scenario.authority(world), evidence=scenario.evidence(world),
                     clock=scenario.clock(world))
    sessions: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        unknown = set(agent.tools) - set(tools)
        if unknown:
            raise ValueError(f"agent {agent.agent_id} references undefined tools {sorted(unknown)}")
        wall.check(agent.system_prompt, where=f"system_prompt[{agent.agent_id}]")
        wall.check([tools[name].schema() for name in agent.tools], where=f"tool_schemas[{agent.agent_id}]")
        sessions[agent.agent_id] = [{"role": "system", "content": agent.system_prompt}]
    decision_tools = frozenset(name for name, spec in tools.items() if spec.decision)
    records: list[dict[str, Any]] = []
    counters = {"model_calls": 0, "tool_calls": 0, "malformed": 0, "consecutive_malformed": 0}
    scenario.opening(env)
    status, detail = "COMPLETED", None
    order = [agent.agent_id for agent in agents]
    by_id = {agent.agent_id: agent for agent in agents}
    try:
        while True:
            pending = [agent_id for agent_id in order if env.inboxes[agent_id]]
            if not pending:
                before = canonical_sha256(env.state)
                quiescent_handled = await scenario.on_quiescent(env)
                _emit_hook_event(env, "on_quiescent", None, before)
                if quiescent_handled:
                    continue
                break
            env.turn += 1
            if env.turn > budget.max_turns:
                raise EpisodeBudgetExceeded("turn budget exceeded")
            agent_id = pending[0]
            order.remove(agent_id)
            order.append(agent_id)
            await _run_turn(by_id[agent_id], sessions[agent_id], tools, env, wall, model, profile,
                            parameters, budget, records, counters)
            before = canonical_sha256(env.state)
            await scenario.after_turn(env, agent_id)
            _emit_hook_event(env, "after_turn", agent_id, before)
    except InvalidModelOutput as exc:
        status, detail = "INVALID_MODEL_OUTPUT", str(exc)
    except EpisodeBudgetExceeded as exc:
        status, detail = "BUDGET_EXCEEDED", str(exc)
    return Trace(status=status, actions=env.actions, events=env.events, records=records,
                 final_state=deepcopy(env.state), agents=agents, decision_tools=decision_tools,
                 malformed_calls=counters["malformed"], error_detail=detail)


def _emit_hook_event(env: "EnvContext", hook: str, agent_id: str | None, state_before: str) -> None:
    """Post-audit amendment ("其他负控"): scenario hooks (after_turn / on_quiescent) mutate world
    state outside the tool path; every hook invocation that CHANGED the state is recorded with
    the responsible hook, actor scope and state before/after hashes, so scheduled world side
    effects are traceable in the ledger rather than invisible."""
    state_after = canonical_sha256(env.state)
    if state_after == state_before:
        return
    env.events.append(make_event(len(env.events) + 1, env.turn, "hook_world_transition",
                                 {"hook": hook, "agent_id": agent_id},
                                 actor=agent_id or "scenario", channel="world",
                                 visibility="environment", action=f"hook:{hook}",
                                 state_before_sha256=state_before, state_after_sha256=state_after))


async def _run_turn(agent: AgentSpec, messages: list[dict[str, Any]], tools: Mapping[str, ToolSpec], env: EnvContext,
                    wall: ObservationFirewall, model: Any, profile: ModelProfile, parameters: Mapping[str, Any],
                    budget: Budget, records: list[dict[str, Any]], counters: dict[str, int]) -> None:
    inbox = env.inboxes[agent.agent_id]
    while inbox:
        text = inbox.popleft()
        wall.check(text, where=f"message->{agent.agent_id}")
        messages.append({"role": "user", "content": text})
        delivery = make_event(len(env.events) + 1, env.turn, "message_delivered",
                              {"to": agent.agent_id, "chars": len(text)},
                              actor=agent.agent_id, channel="inbox", visibility="model_visible",
                              parent_seq=env._last_delivery_seq.get(agent.agent_id))
        env.events.append(delivery)
        env._last_delivery_seq[agent.agent_id] = delivery["seq"]
    schemas = tuple(tools[name].schema() for name in agent.tools)
    for _ in range(budget.max_steps_per_turn):
        counters["model_calls"] += 1
        if counters["model_calls"] > budget.max_model_calls:
            raise EpisodeBudgetExceeded("model-call budget exceeded")
        request = ModelRequest(tuple(deepcopy(messages)), deepcopy(dict(parameters)), deepcopy(schemas),
                               {"agent_id": agent.agent_id, "role": agent.role, "organization": agent.organization})
        started = time.perf_counter()
        response: ModelResponse = await model.generate(profile, request)
        elapsed = time.perf_counter() - started
        records.append(_record(agent, request, response, env.turn, elapsed))
        if response.finish_reason == "length":
            raise InvalidModelOutput("truncated model output (finish_reason=length)")
        if not ((response.text or "").strip() or response.tool_calls):
            raise InvalidModelOutput("empty model output")
        calls = list(response.tool_calls)
        if any(not isinstance(call, Mapping) or not isinstance(call.get("function", call), Mapping)
               for call in calls):
            raise InvalidModelOutput("malformed tool-call structure")
        assistant_message = {"role": "assistant", "content": response.text or ""}
        if profile.provider == "deepseek" and response.reasoning_content is not None:
            assistant_message["reasoning_content"] = response.reasoning_content
        if calls:
            assistant_message["tool_calls"] = deepcopy(calls)
        messages.append(assistant_message)
        if not calls:
            return
        for index, call in enumerate(calls):
            # budget is enforced before execution so a call is either fully
            # executed and recorded, or never run — never executed unrecorded
            if counters["tool_calls"] >= budget.max_tool_calls:
                raise EpisodeBudgetExceeded("tool-call budget exceeded")
            counters["tool_calls"] += 1
            call_id = str(call.get("id") or f"call-{len(records)}-{index}")
            state_before = canonical_sha256(env.state)
            result, status, name, args = _execute(call, agent, tools, env)
            state_after = canonical_sha256(env.state)
            if status == "malformed":
                counters["malformed"] += 1
                counters["consecutive_malformed"] += 1
            else:
                counters["consecutive_malformed"] = 0
            action = ActionRecord(len(env.actions) + 1, env.turn, agent.agent_id, name, args, status, result,
                                  state_before_sha256=state_before, state_after_sha256=state_after)
            env.actions.append(action)
            env.events.append(make_event(len(env.events) + 1, env.turn, "tool_executed",
                                         {"tool": name, "status": status, "action_seq": action.seq},
                                         actor=agent.agent_id, channel="tool_result",
                                         visibility="model_visible", action=name,
                                         authority_reference=_authority_reference(tools, name, args, status, env, agent.agent_id, env.turn),
                                         state_before_sha256=state_before, state_after_sha256=state_after,
                                         effects={"result_status": result.get("status")} if isinstance(result, dict) else None,
                                         error=None if status == "ok" else str(result.get("message", ""))[:200],
                                         parent_seq=env._last_delivery_seq.get(agent.agent_id)))
            if counters["consecutive_malformed"] >= MAX_CONSECUTIVE_MALFORMED:
                raise InvalidModelOutput(f"{MAX_CONSECUTIVE_MALFORMED} consecutive malformed tool calls")
            wall.check(result, where=f"tool_result[{name}]->{agent.agent_id}")
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": json.dumps(result, sort_keys=True, ensure_ascii=False)})
    # the per-turn step budget is spent; the agent's turn ends without a closing text


def _execute(call: Mapping[str, Any], agent: AgentSpec, tools: Mapping[str, ToolSpec],
             env: EnvContext) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    function = call.get("function", call)
    name = str(function.get("name", ""))
    raw = function.get("arguments", {})
    try:
        args = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"status": "error", "message": "arguments are not valid JSON"}, "malformed", name, {}
    if not isinstance(args, dict):
        return {"status": "error", "message": "arguments must be a JSON object"}, "malformed", name, {}
    if name not in agent.tools:
        return {"status": "error", "message": f"operation '{name}' is not available to you"}, "malformed", name, args
    spec = tools[name]
    try:
        jsonschema.validate(args, dict(spec.parameters))
    except jsonschema.ValidationError as exc:
        return {"status": "error", "message": f"invalid arguments: {exc.message}"}, "malformed", name, args
    if spec.authority_scope is not None:
        if env.authority is None:
            # a declared authority requirement without a ledger is a world-assembly error,
            # not a model error: fail the episode loudly rather than silently waiving the check
            raise ValueError(f"tool {name} declares authority_scope but the episode has no AuthorityLedger")
        action_token, resource_template = spec.authority_scope
        audience = args.get(spec.audience_from_arg) if spec.audience_from_arg else None
        decision = env.authority.check(actor=agent.agent_id, action=action_token,
                                       resource=_render_resource(resource_template, args),
                                       audience=audience, at_turn=env.turn)
        if not decision.granted:
            return {"status": "error",
                    "message": f"not authorized: {decision.reason}"}, "error", name, args
    try:
        result = dict(spec.handler(ToolContext(agent.agent_id, env), args))
    except ToolError as exc:
        return {"status": "error", "message": str(exc)}, "error", name, args
    result.setdefault("status", "ok")
    return result, "ok" if result["status"] == "ok" else "error", name, args


def _authority_reference(tools: Mapping[str, ToolSpec], name: str, args: Mapping[str, Any],
                         status: str, env: EnvContext, actor: str, turn: int) -> str | None:
    """Grant id supporting the call, or a denial marker — ledger annotation for the event."""
    spec = tools.get(name)
    if spec is None or spec.authority_scope is None or env.authority is None or status == "malformed":
        return None
    action_token, resource_template = spec.authority_scope
    audience = args.get(spec.audience_from_arg) if spec.audience_from_arg else None
    decision = env.authority.check(actor=actor, action=action_token,
                                   resource=_render_resource(resource_template, args),
                                   audience=audience, at_turn=turn)
    return decision.grant_id if decision.granted else f"denied:{decision.reason}"


def _render_resource(template: str, args: Mapping[str, Any]) -> str:
    try:
        return template.format(**args)
    except (KeyError, IndexError, ValueError):
        return template


def _record(agent: AgentSpec, request: ModelRequest, response: ModelResponse, turn: int,
            elapsed_seconds: float) -> dict[str, Any]:
    snapshot = {"messages": deepcopy(list(request.messages)), "tools": deepcopy(list(request.tools)),
                "parameters": deepcopy(dict(request.parameters)), "role_metadata": deepcopy(dict(request.role_metadata))}
    record = {"agent_id": agent.agent_id, "turn": turn, "request": snapshot, "request_sha256": canonical_sha256(snapshot),
              "response": {"text": response.text, "tool_calls": deepcopy(list(response.tool_calls)),
                           "finish_reason": response.finish_reason, "model_id": response.model_id,
                           "usage": deepcopy(dict(response.usage)),
                           "provider_metadata": deepcopy(dict(response.provider_metadata)),
                           "reasoning_content": response.reasoning_content,
                           "reasoning_details": deepcopy(response.reasoning_details) if response.reasoning_details is not None else None,
                           # wall-clock duration of this provider call: the direct signal for
                           # abnormally-long-reasoning diagnostics alongside usage/finish_reason
                           "elapsed_seconds": round(elapsed_seconds, 3)}}
    journal = AttemptJournal.current()
    if journal is not None:
        journal.record(record)
    return record
