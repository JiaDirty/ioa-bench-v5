# 19 — Testing, CI and Quality Gates

## 1. Goal

The benchmark must distinguish implementation defects from model behavior. CI therefore validates contracts, storage, provider adapters, scenario semantics, scoring and replay independently before formal model runs.

## 2. Required test layers

1. **Contract tests** — JSON Schema, YAML parsing, content hashing, semantic validation.
2. **Pure unit tests** — scoring math, budgets, lifecycle, dedup, truth arithmetic, difficulty features.
3. **Adapter contract tests** — ModelPort/Registry/A2A/MCP/Sandbox behavior using mocks or local test endpoints.
4. **Storage migration tests** — apply SQLite schemas to clean temporary DBs; optional scale-out migrations tested only in their profile.
5. **Golden scorer tests** — every scorer has perfect, total failure, partial/recovery, zero denominator, missing evidence and invalid exposure fixtures.
6. **Replay tests** — recorded case reconstructs the same observable timeline and scorer inputs.
7. **End-to-end smoke** — one tiny multi-agent case with mock model; one opt-in real AIHubMix connectivity smoke.
8. **Dataset generator tests** — generated candidate cannot alter programmatic truth; rejected candidates retain rejection reason.
9. **Isolation tests** — tested-agent environment lacks Oracle path/handle and public-web tool.

## 3. Real-provider tests

Do not make routine offline unit tests depend on AIHubMix availability. Separate opt-in integration tests require `AIHUBMIX_API_KEY`. They validate exact live model resolution, minimal generation, tool/structured capability where needed, and provider error parsing.

## 4. Formal dataset gates

Before `FROZEN`:
- 100% schema-valid;
- 100% Oracle-consistent;
- 100% exposure-reachable in risk cases;
- 100% control-solvable according to deterministic precheck;
- zero detected Oracle leakage;
- semantic validation policy satisfied;
- target mechanism/world/difficulty coverage satisfied;
- duplicate rate below configured threshold;
- manifest/hash/provenance complete.

## 5. Formal run gates

Before scores enter reports:
- frozen Run Manifest exists;
- exact tested model resolved;
- exposure proof exists for risk case;
- required telemetry complete;
- scorer/judge versions match manifest;
- sandbox/replay state persisted;
- no infrastructure failure remains unresolved.

## 6. Regression policy

Every fixed bug gets a regression test. If a bug can alter formal results, perform impact analysis and invalidate/re-run all affected results under a bumped benchmark component version.
