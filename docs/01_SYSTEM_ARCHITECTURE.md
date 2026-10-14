# 01 — System Architecture

## 1. Architecture objective

The architecture exists to isolate and measure **model behavior** under IoA conditions. It is intentionally not a production security architecture benchmark.

```text
Evaluation / Benchmark Plane
  ScenarioCompiler ─ DatasetManager ─ RunScheduler ─ Scoring/Analysis
          │                 │               │              │
          └────────────── hidden Oracle / manifests ──────┘
                               │
                        controlled exposure
                               ▼
Reference IoA Environment
  Org A                   Org B                   Org C
  ┌──────────┐            ┌──────────┐            ┌──────────┐
  │ Agent A1 │◄──────────►│ Agent B1 │◄──────────►│ Agent C1 │
  │ Agent A2 │    A2A     │ Agent B2 │    A2A     │ Agent C2 │
  └────┬─────┘            └────┬─────┘            └────┬─────┘
       │                       │                       │
       ├── Registry / Discovery / Router / Delegation ┤
       │                       │                       │
       └────────────────── MCP Sandbox Tools ─────────┘
                               │
                         observable actions
                               ▼
Telemetry / Replay Plane
  events + model I/O + messages + tools + decisions + provenance
                               │
                               ▼
                      Safety + Utility results
```

## 2. Planes

### 2.1 Benchmark Control Plane
Owns case selection, dataset versions, run manifests, action budgets, exposure scheduling, hidden truth, scoring and checkpoint/resume. Tested agents must not read it.

### 2.2 Reference IoA Plane
Provides controlled organizations, agents, discovery, identity claims, delegation context, protocol semantics, reputation/incentive signals, shared knowledge and tool resources.

### 2.3 Sandbox Action Plane
Provides synthetic business APIs whose state changes are real within the sandbox. A model must be able to cause observable side effects such as `invoice.update`, `approval.submit`, `message.forward`, `service.deploy`, or `record.modify` without touching real assets.

### 2.4 Observation/Replay Plane
Captures all information needed to reconstruct what happened. It may include raw model input/output because formal worlds are synthetic, but secrets and provider credentials must be redacted.

### 2.5 Oracle Plane
Contains authoritative hidden truth: real role/qualification, true capability, valid authority envelope, canonical protocol meaning, true synthetic facts, intended topology, baseline norm, task answer and utility function.

## 3. Local v1 deployment

v1 MUST run on one workstation without Docker. Preferred process topology:

```text
ioabench CLI/orchestrator
├── local Registry/Router service (process or in-proc server)
├── local A2A agent endpoints (multiple independent agent sessions)
├── local MCP sandbox servers
├── local synthetic business services
├── local dashboard/API
├── control.db
├── sut.db
├── oracle.db   [never exposed to agent processes]
├── telemetry.db
└── data/ datasets, artifacts, reports, replay blobs
```

The implementation may initially run services in one Python process for developer smoke tests, but formal runs must preserve logical context/credential isolation between tested agents.

## 4. Tested-agent architecture

Each tested agent owns:
- immutable agent id, org/trust-domain id, role id;
- neutral role prompt and policy context;
- independent model conversation/session;
- private working memory;
- A2A client/server adapter;
- MCP/tool client adapter;
- discovery/verification/delegation clients;
- action budget counters;
- telemetry instrumentation.

The same model may back all normal participating agents, but their contexts MUST NOT be shared implicitly.

## 5. Infrastructure stimulus vs score

Example: a Registry returns a malicious but plausible record. The Registry fault is an exposure. The model score depends on whether a tested agent verifies, accepts, selects, delegates to, forwards from, or recovers from that record. Infrastructure failure alone is never model failure.

## 6. Open-source reuse

Use real A2A/MCP SDK semantics where stable. Use AGNTCY adapters optionally for integration realism, not as mandatory v1 services. A lightweight reference Registry/Identity/Delegation implementation is acceptable because the research target is model behavior and controlled stimuli.

## 7. Port boundaries

Core code depends on ports, never concrete providers:
`ModelPort`, `AgentRuntimePort`, `RegistryPort`, `IdentityPort`, `DelegationPort`, `ProtocolPort`, `ToolPort`, `SandboxPort`, `TelemetryPort`, `OraclePort`, `DatasetStorePort`, `RunStorePort`, `ArtifactStorePort`, `JudgePort`.

## 8. Public Internet isolation

Formal tested-agent runs must not grant browser/public-web access. If a case needs a web-like artifact, it must be materialized inside the synthetic world/sandbox before the run.
