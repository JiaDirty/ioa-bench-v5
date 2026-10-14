# 02 — Data, Truth, Event and Replay Model

## 1. Four stores, four meanings

v1 uses logically and physically separate local stores:

1. `control.db` — experiment definitions, run state, frozen manifests, scores.
2. `sut.db` — world state visible or actionable by the reference IoA.
3. `oracle.db` — hidden authoritative truth and expected invariants.
4. `telemetry.db` — append-oriented observations, model I/O references and replay index.

Datasets/artifacts/reports live in versioned filesystem trees. Oracle paths/handles MUST never be available in tested-agent process environments.

## 2. Identity and claims

Never conflate claims with truth.

`AgentClaim` may state:
- organization membership;
- skill/capability;
- credential/qualification;
- representative authority;
- reliability/reputation assertions.

Oracle has independent truth records. A signed Agent Card proves integrity/source under the scenario's rules; it does not automatically prove a claimed capability.

## 3. Delegation model

A delegation edge contains:
`delegation_id, parent_id, issuer, subject, resource, action_scope, audience, valid_from, valid_until, max_depth, conditions`.

Oracle stores the valid envelope. SUT-visible delegation may be correct, ambiguous, expanded, translated or misleading depending on the case.

## 4. Knowledge model

Knowledge is represented as propositions/claims, not only chat messages.

`CanonicalFact` is hidden truth. `ClaimInstance` is a surface statement with source/provenance, confidence, evidence references and relation to a canonical proposition. Paraphrase/endorsement/forward edges permit propagation analysis.

## 5. Model interaction record

Every model call record must capture:
- run/case/agent ids;
- tested/generator/validator/judge role;
- provider and exact model id;
- prompt template id/version;
- system/developer/user/tool message hashes and replay references;
- sampling parameters actually sent;
- request/response timestamps;
- response text/tool call/structured result references;
- token/usage/cost metadata when returned;
- provider request/trace id when available;
- retry attempt and error class.

Private hidden chain-of-thought is not required. Scoring must rely on observable outputs/actions.

## 6. Normalized event lifecycle

All suites should map behavior onto:
`EXPOSURE -> RECOGNITION -> VERIFICATION -> DECISION -> ACTION -> RECOVERY`.

Event types include:
- `risk.exposed`
- `agent.message.sent/received`
- `agent.discovery.query/result`
- `agent.identity.verify`
- `agent.capability.verify`
- `agent.delegation.create/accept/reject`
- `agent.decision`
- `tool.call/request/result`
- `knowledge.claim.accept/reject/forward`
- `reputation.read/update`
- `incentive.signal`
- `protocol.negotiation/translation`
- `recovery.detect/correct/replan`
- `task.completed/failed/refused`

## 7. Replay bundle

A formal case replay bundle must resolve:
- frozen scenario + dataset record;
- synthetic-world snapshot;
- all tested-agent prompt versions;
- all model request/response records;
- A2A/MCP messages;
- sandbox tool state transitions;
- injected stimulus state;
- Oracle comparison references;
- scorer inputs, evidence ids and outputs;
- final utility result.

## 8. Provenance

Every generated datum must be traceable to generator version, prompt template, provider/model, parameters, parent template/world, validator decisions, repair attempts and content hashes.

## 9. Immutability

Frozen scenario/dataset/scorer artifacts are content-addressed. Updating them creates a new semantic version. Historical run manifests reference exact hashes and remain interpretable forever.
