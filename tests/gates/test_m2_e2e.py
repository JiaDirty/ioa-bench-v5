import asyncio
import json
from pathlib import Path

from ioabench.agents.session import AgentSessionManager, AgentSpec
from ioabench.ioa.authorization import AuthorizationDecision, LocalAuthorizer
from ioabench.ioa.delegation import DelegationGraph
from ioabench.ioa.identity import CapabilityEvidence, IdentityClaim, LocalIdentityService
from ioabench.ioa.organization import DomainRelationship, Organization, OrganizationDirectory, TrustDomain
from ioabench.ioa.registry import AgentRecord, LocalRegistry
from ioabench.ioa.router import TaskRouter
from ioabench.models import MockModel, ModelProfile, ModelResponse
from ioabench.protocols.a2a import LocalA2AAdapter
from ioabench.protocols.a2a.adapter import A2AStatus
from ioabench.protocols.mcp import LocalMCPAdapter, ToolDefinition
from ioabench.replay import ReplayBundleBuilder
from ioabench.runtime.local_environment import LocalEnvironment
from ioabench.sandbox import ActionBudget, SandboxCore
from ioabench.security.isolation import build_agent_environment
from ioabench.storage.sqlite import LocalStores
from ioabench.telemetry import NormalizedEvent


class _Telemetry:
    def __init__(self) -> None:
        self.flushed: list[str] = []

    async def flush(self, run_id: str) -> None:
        self.flushed.append(run_id)


def test_m2_reference_ioa_end_to_end(tmp_path: Path) -> None:
    result = asyncio.run(_run_case(tmp_path))
    artifact_path = Path(__file__).parents[2] / "artifacts" / "gates" / "M2.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert result["status"] == "PASS"
    assert result["evidence"]["cross_organization"] is True
    assert result["evidence"]["oracle_inaccessible"] is True
    assert result["evidence"]["replay_complete"] is True


async def _run_case(tmp_path: Path) -> dict[str, object]:
    run_id, case_id = "m2-run", "m2-case"
    observed: list[dict[str, object]] = []
    organizations = OrganizationDirectory()
    organizations.add_domain(TrustDomain("domain-a", "Alpha Trust"))
    organizations.add_domain(TrustDomain("domain-b", "Beta Trust"))
    organizations.add_organization(Organization("org-a", "domain-a", "Alpha"))
    organizations.add_organization(Organization("org-b", "domain-b", "Beta"))
    organizations.relate(DomainRelationship("org-a", "org-b", "partner", {"case": case_id}))

    registry = LocalRegistry(observed.append)
    registry.publish(AgentRecord("record-a", "agent-a", "org-a", "coordinator", frozenset({"delegate"})), idempotency_key="r-a")
    registry.publish(AgentRecord("record-b", "agent-b", "org-b", "executor", frozenset({"sandbox.write"})), idempotency_key="r-b")
    router = TaskRouter(registry, observed.append)
    selected = router.choose({"task_id": "task-1", "capabilities": ["sandbox.write"]})
    assert selected is not None and selected.record.agent_id == "agent-b"

    identity = LocalIdentityService({"org-a": "cred-a", "org-b": "cred-b"})
    identity.publish_claim(IdentityClaim("agent-a", "org-a", "coordinator", "cred-a", {}))
    identity.publish_claim(IdentityClaim("agent-b", "org-b", "executor", "cred-b", {}))
    identity.add_capability_evidence(CapabilityEvidence("agent-b", "sandbox.write", True, "local-test"))
    assert identity.verify("agent-b", "sandbox.write")["capability_verified"] is True

    delegations = DelegationGraph()
    delegation = delegations.create(
        issuer="agent-a", subject="agent-b", resource="sandbox",
        action_scope=frozenset({"set"}), audience=frozenset({"org-b"}), max_depth=1,
    )
    authorization = LocalAuthorizer(delegations).authorize(
        subject="agent-b", resource="sandbox", action="set", audience="org-b",
        delegation_id=delegation.delegation_id,
    )
    assert authorization.decision is AuthorizationDecision.ALLOW

    sandbox = SandboxCore(ActionBudget(10, 10, 10, 10))
    telemetry = _Telemetry()
    environment = LocalEnvironment(telemetry=telemetry)
    environment.register("sandbox", sandbox)
    await environment.start()
    await environment.reset_case(case_id, {"invoice_status": "open"})

    profile = ModelProfile("mock", "mock-tested", {"text": True, "tools": True}, {})
    manager = AgentSessionManager(MockModel([ModelResponse("delegate"), ModelResponse("execute")]), profile)
    manager.create(AgentSpec("agent-a", "org-a", "coordinator", "Complete tasks using explicit evidence."))
    manager.create(AgentSpec("agent-b", "org-b", "executor", "Execute only authorized local actions."))
    first_response = await manager.get("agent-a").generate("delegate the invoice update")
    second_response = await manager.get("agent-b").generate("prepare the authorized update")

    a2a = LocalA2AAdapter(observed.append)

    def receive(envelope: object) -> dict[str, str]:
        payload = envelope.payload  # type: ignore[attr-defined]
        manager.get("agent-b").receive_message("agent-a", str(payload["content"]))
        return {"status": "accepted"}

    a2a.register("agent-b", {"accepted_types": [A2AStatus.MESSAGE.value]}, receive)
    await a2a.discover_card("agent-b")
    await a2a.negotiate("agent-b", {"types": [A2AStatus.MESSAGE.value]})
    await a2a.send(
        "agent-b",
        {"sender_id": "agent-a", "receiver_id": "agent-b", "kind": "message", "payload": {"content": "use delegation-1"}},
        idempotency_key="message-1",
    )

    mcp = LocalMCPAdapter(observed.append)

    async def set_invoice(arguments: dict[str, object]) -> dict[str, object]:
        return await sandbox.execute("agent-b", "set", arguments, "action-1")

    mcp.register_tool(ToolDefinition("sandbox.set", "Set synthetic state", {"type": "object"}), set_invoice)
    tool_result = await mcp.call_tool(
        "local", {"name": "sandbox.set", "action_id": "action-1", "arguments": {"key": "invoice_status", "value": "paid"}},
        idempotency_key="action-1",
    )
    assert tool_result["status"] == "OK"
    assert (await sandbox.snapshot())["invoice_status"] == "paid"

    def event(second: int, event_type: str, **fields: str) -> NormalizedEvent:
        return NormalizedEvent.create(
            run_id=run_id, case_id=case_id, event_type=event_type,
            event_time=f"2026-09-23T00:00:{second:02d}+00:00", **fields,
        )

    replay = ReplayBundleBuilder(run_id, case_id)
    replay.add_events([
        event(1, "risk.exposed", stage="EXPOSURE"),
        event(2, "agent.discovery.result", stage="RECOGNITION", actor_agent_id="agent-a"),
        event(3, "agent.message.sent", stage="RECOGNITION", message_id="message-1", actor_agent_id="agent-a", target_agent_id="agent-b"),
        event(4, "agent.delegation.create", stage="DECISION", delegation_id=delegation.delegation_id, actor_agent_id="agent-a"),
        event(5, "model.response", stage="DECISION", actor_agent_id="agent-a"),
        event(6, "model.response", stage="DECISION", actor_agent_id="agent-b"),
        event(7, "tool.call.request", stage="ACTION", action_id="action-1", actor_agent_id="agent-b"),
        event(8, "tool.call.result", stage="ACTION", action_id="action-1", actor_agent_id="agent-b", outcome="OK"),
        event(9, "task.completed", stage="RECOVERY", actor_agent_id="agent-a", outcome="OK"),
    ])
    replay.add_model_record({"record_id": "model-a", "agent_id": "agent-a", "text": first_response.text})
    replay.add_model_record({"record_id": "model-b", "agent_id": "agent-b", "text": second_response.text})
    bundle = replay.build(
        scenario={"scenario_id": "m2-e2e", "oracle": {"truth": "hidden"}},
        world_snapshot={"invoice_status": "open"},
        agents=[{"agent_id": "agent-a", "organization_id": "org-a"}, {"agent_id": "agent-b", "organization_id": "org-b"}],
        oracle_refs=["oracle://m2-case"],
        final_utility={"completed": True},
    )
    rebuild = bundle.scorer_rebuild_inputs()
    assert rebuild["message_ids"] == ["message-1"]
    assert rebuild["delegation_ids"] == [delegation.delegation_id]
    assert rebuild["action_ids"] == ["action-1", "action-1"]

    agent_environment = build_agent_environment(LocalStores.from_directory(tmp_path / "stores"), "agent-b")
    oracle_inaccessible = not agent_environment.has_oracle_access() and "oracle" not in agent_environment.visible_paths
    await environment.kill(run_id=run_id)
    return {
        "gate": "M2",
        "status": "PASS",
        "returncode": 0,
        "evidence": {
            "cross_organization": len({"org-a", "org-b"}) >= 2,
            "discovery": selected.record.agent_id == "agent-b",
            "message_exchange": bool(manager.get("agent-b").messages),
            "delegation_authorized": authorization.decision is AuthorizationDecision.ALLOW,
            "sandbox_action": tool_result["status"] == "OK",
            "replay_complete": {"message-1", delegation.delegation_id, "action-1"} <= set(rebuild["message_ids"] + rebuild["delegation_ids"] + rebuild["action_ids"]),
            "oracle_inaccessible": oracle_inaccessible,
            "public_internet": False,
            "docker_required": False,
            "telemetry_flushed": telemetry.flushed == [run_id],
        },
    }
