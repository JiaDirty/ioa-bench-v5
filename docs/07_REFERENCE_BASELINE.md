# 07 — External Reference Baseline

> This file records intended external baselines; Codex MUST verify current official documentation during implementation rather than relying on stale version assumptions.

## A2A
Use A2A as the primary agent-to-agent interoperability baseline where practical. The benchmark relies on Agent Card/discovery/task/message semantics but does not treat A2A itself as the scored security target.

## MCP
Use MCP as the primary agent-to-tool protocol baseline for sandbox tools where practical. Tool calls must remain local/synthetic in formal runs.

## AGNTCY
AGNTCY Directory/OASF/Identity/SLIM/Observability are useful integration references/profiles. They are optional for local v1 because the reference environment must remain controllable and easy to run on one workstation without Docker.

## AIHubMix
Use AIHubMix as v1 model gateway through a provider adapter. Discover and validate live model ids/capabilities before formal freeze. Never commit API keys.

## Storage
Local v1 normative profile: separate SQLite databases + versioned filesystem artifacts. PostgreSQL/ClickHouse remain optional scale-out contracts.
