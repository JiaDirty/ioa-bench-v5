# 15 — Model Runtime and AIHubMix Integration

## 1. Role of AIHubMix

AIHubMix is the v1 model-provider gateway for:
1. tested agents;
2. dataset generators;
3. semantic validators;
4. semantic judges;
5. synthetic personas.

The provider is NOT the domain model. All calls pass through `ModelPort`.

## 2. Live model discovery

At development/generation time the adapter MAY query AIHubMix's live model catalog. At formal run start, resolve the requested model id and capabilities, then freeze the exact id and endpoint protocol in the Run Manifest.

Never assume a model id from documentation/memory is still valid. A missing/retired tested model is a configuration blocker, not permission to silently substitute another model.

## 3. v1 tested model

Requested canonical v1 tested model: `deepseek-v4.1-flash` (subject to live provider-id validation when the run is frozen).

Candidate generator/validator models may include currently available AIHubMix DeepSeek, GLM, Qwen, GPT, Claude and Gemini models. The pool is configuration, not source code truth.

## 4. Client profile

Default OpenAI-compatible profile:
- base URL configured, default `https://aihubmix.com/v1`;
- API key from `AIHUBMIX_API_KEY`;
- non-streaming structured generation preferred for dataset generation when supported;
- endpoint/capability selected by live model metadata;
- request timeout, retry and backoff are bounded and configurable.

## 5. Provider failure semantics

Classify at least:
- authentication/configuration;
- rate limit;
- transient 5xx/network;
- model unavailable/retired;
- malformed response;
- context length;
- unsupported parameter/tool capability;
- ambiguous completion state.

For formal tested-model runs: retry eligible failures; if exhausted, mark `INFRASTRUCTURE_FAILURE` and retry the same frozen model later. Never switch model within the run.

## 6. Sampling fairness

Formal benchmark uses one frozen base sampling profile. Per-suite overrides are allowed only when technically indispensable and must be explicit/versioned. Unsupported provider parameters are omitted and recorded as compatibility differences.

## 7. Role separation

Provenance must make generator, validator, judge, synthetic-persona and tested-model calls distinguishable. Where feasible, data generation/validation should not use the same model identity as the tested model for a released dataset intended for cross-model evaluation.

## 8. Caching and replay

Development may cache generation/validation calls by normalized request hash. Formal tested-model responses must be recorded but not reused as if newly sampled unless running an explicit replay mode.

## 9. Cost accounting

Cost is not a safety score. Record model calls, input/output tokens, provider-reported usage, latency and estimated/actual cost separately. Data-generation budget controls may halt generation but may not lower quality thresholds.
