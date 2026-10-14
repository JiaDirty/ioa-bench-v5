# 05 — Implementation Roadmap and Acceptance

## Strategy
Build model-centric vertical slices. Do not build production-grade distributed infrastructure before one tested-model case can execute and be replayed.

## M0 — Core repository/local storage
Deliver package skeleton, local config, four-store SQLite profile, lifecycle, Run Manifest, schemas, state/work queue, test tooling.
Acceptance: schemas validate; SQLite migrations apply on clean temp dirs; lifecycle/checkpoint tests pass.

## M1 — AIHubMix + model runtime
Deliver `ModelPort`, AIHubMix adapter, live model validation, independent tested-agent sessions, mock/replay model, usage/error recording.
Acceptance: requested model can be validated/called; two agents using same model have isolated contexts; provider failure never silently swaps tested model.

## M2 — Reference IoA + sandbox
Deliver local Registry/Router/Identity/Delegation primitives, A2A adapter/profile, MCP sandbox tools, 2–3 organizations, world snapshots, action budgets, full telemetry.
Acceptance: multi-agent task discovers/delegates/calls local tool and replays end-to-end without Oracle access.

## M3 — Data-generation framework
Deliver dataset manifest/schema, mechanism template API, generator router, validators, provenance, dedup, difficulty calibration, freeze/versioning.
Acceptance: one T311 generator creates >target candidates, rejects defects with reasons, freezes a valid mini dataset without manual editing.

## M4 — T311 vertical slice
Deliver 4–6 T311 mechanisms, 2–3 worlds, Easy/Medium/Hard, control pairs, scorer, replay, dashboard view.
Acceptance: tested model behavior is scored from observable verification/selection/action; injected Registry/claim condition alone cannot count as model failure.

## M5 — T312–T323
Complete trust/authorization and protocol suites using the same model-centric pattern.

## M6 — T331–T343
Complete propagation/inference/knowledge dynamics. Multiple participating normal agents use the tested model; scripted adversaries remain canonical.

## M7 — T351–T353
Complete incentive/reputation/power dynamics with explicit programmatic truth and counterfactuals.

## M8 — T361–T363 simulation
Implement synthetic personas and longitudinal sessions. All results `SIMULATION_ONLY`.

## M9 — Formal datasets
For each Txxx, generate/calibrate/freeze target ~90 qualified cases, normally 30/30/30. Generation is suite-by-suite, not all upfront.

## M10 — Full benchmark release candidate
Run `deepseek-v4.1-flash` through all supported frozen suites, checkpoint/resume, automatic reports/dashboard/replay, representative failures and limitations.

## v1 Definition of Done
- 18 generator pipelines;
- 18 frozen datasets (~1620 total target cases);
- 18 executable suites;
- local reference IoA and sandbox;
- AIHubMix-tested-model runtime;
- full observable stage scoring + separate utility;
- one-command suite-all execution;
- complete replay;
- local dashboard;
- automatic research report;
- T361–T363 visibly simulation-only.
