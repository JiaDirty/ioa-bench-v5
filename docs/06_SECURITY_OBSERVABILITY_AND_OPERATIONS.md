# 06 — Security, Observability and Local Operations

## 1. Threat boundary

The benchmark intentionally creates deceptive/malicious synthetic agents and content. Keep all actions inside local synthetic sandboxes. Tested agents have no public Internet or real-account credentials in formal runs.

## 2. Secrets

`AIHUBMIX_API_KEY` and any local service credentials are environment/secret-store values only. Never commit, log, place in datasets, prompt traces or replay artifacts. Redaction occurs before persistence.

## 3. Oracle isolation

`oracle.db` must be opened only by evaluator-side code. Tested-agent runtime receives no Oracle path/handle. Unit/integration tests must assert this boundary.

## 4. Observability completeness

A formal run must capture enough events to prove risk exposure and behavior stage transitions. Missing required telemetry yields `INVALID_RUN`, not a safe score.

## 5. Local process isolation

Formal mode should use separate logical sessions/process boundaries for agents when practical. Independent context/memory isolation is mandatory even if optimized into one process.

## 6. Kill switch

Provide a command/API to halt scheduling, cancel active loops, prevent further sandbox side effects, flush telemetry and persist recoverable checkpoint state.

## 7. Data retention

Synthetic prompts/messages may be retained for replay. Credentials and API keys may not. Rejected dataset candidates may be retained with provenance and rejection reason.

## 8. Operations

Health checks include provider connectivity, writable local stores, schema versions, sandbox reset ability, model capability validation and disk-space threshold. Formal run must fail preflight before consuming cases if critical checks fail.
