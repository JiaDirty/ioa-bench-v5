# 08 — Python API Contract

## 1. Architectural rule

Benchmark-owned domain code must not import provider SDKs. Concrete A2A/MCP/AIHubMix/AGNTCY/database implementations live under adapters.

## 2. Required packages

`ioabench.core`, `models`, `agents`, `worlds`, `sandbox`, `datasets`, `generation`, `scenarios`, `exposures`, `oracle`, `telemetry`, `scoring`, `judges`, `analysis`, `scheduler`, `reports`, `adapters`, `api`.

## 3. Core ports

### ModelPort
Resolve/validate model; generate structured/unstructured response; expose capability metadata; return provider usage/error metadata. Tested-model substitution after manifest freeze is forbidden.

### AgentRuntimePort
Create independent agent session; execute one step/loop under action budget; send/receive A2A messages; call tools; snapshot/replay session state.

### RegistryPort
Publish/get/discover synthetic Agent records. Registry claims are not Oracle truth.

### IdentityPort
Expose/verify scenario credentials/identity evidence without deciding capability truth unless the scenario explicitly defines that evidence.

### DelegationPort
Create/read/validate SUT-visible delegation envelopes.

### SandboxPort
Execute synthetic actions idempotently and return state transition references.

### OraclePort
Evaluator-only access to hidden truth. No adapter implementing tested-agent runtime may receive this port.

### TelemetryPort
Append normalized observable events and model-call records.

### JudgePort
Classify only versioned semantic rubrics; return structured verdict/evidence/confidence/disagreement metadata.

### DatasetGeneratorPort
Produce candidate skeleton/material from a DatasetManifest; never freeze directly.

### DatasetValidatorPort
Return structured validation findings; no silent mutation.

### SchedulerPort
Expand run matrix, checkpoint, resume, invalidate/retry by failure class.

## 4. Idempotency

Sandbox mutations, run transitions, artifact writes, exposure activation and scheduler state changes require idempotency keys.

## 5. Error classes

At minimum distinguish `ConfigurationError`, `ProviderTransientError`, `ProviderPermanentError`, `ModelUnsupportedError`, `ScenarioInvalidError`, `ExposureInvalidError`, `OracleViolationError`, `TelemetryIncompleteError`, `JudgeUnresolvedError`, `InfrastructureFailure`, `RunInvalidError`.

## 6. Contracts

Machine-readable `.pyi` files under `contracts/python/` are normative when more specific than prose.
