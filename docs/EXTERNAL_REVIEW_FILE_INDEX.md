# IoA-Bench External Review File Index

This index is a navigation aid for the current read-only handoff snapshot. Source code and reproducible artifacts take precedence over historical PASS wording.

## Read first
- `AGENTS.md`: normative research boundaries and v1 rules.
- `docs/PROJECT_HANDOFF_CURRENT_STATE.md`: current state, history, architecture, limitations, and next-stage strategy.
- `artifacts/handoff/CURRENT_PROJECT_INVENTORY.json`: machine-readable snapshot inventory.
- `state/PROJECT_STATE.yaml`, `state/WORK_QUEUE.yaml`, `state/WORK_QUEUE_VALIDATION.json`: governance state; historical `done` does not imply current construct validity.

## Architecture and runtime
- `docs/01_SYSTEM_ARCHITECTURE.md`, `docs/02_DATA_AND_EVENT_MODEL.md`, `docs/16_REFERENCE_IOA_WORLDS_AND_SANDBOX.md`: Reference IoA design.
- `src/ioabench/ioa/`, `src/ioabench/protocols/`, `src/ioabench/sandbox/`: reusable infrastructure.
- `src/ioabench/runtime/offline_run.py`, `src/ioabench/suites/_vertical.py`: legacy generic runtime retained for historical runs.
- `src/ioabench/runtime/construct_runtime.py` and the suite archetype modules: current construct runtime base and suite-specific implementations for all 18 suites.
- `src/ioabench/suites/`: suite generators, scenarios and scorers; current offline acceptance is recorded in the Phase A V2 gate.

## Research decisions and audit
- `docs/04_EVALUATION_18_TESTS.md`, `docs/10_TEST_DATA_RECIPES_18_SUITES.md`: canonical suite definitions and data recipes.
- `docs/18_DESIGN_DECISIONS_REGISTER.md`: research decisions.
- `docs/CONSTRUCT_IMPLEMENTATION_GAP_AUDIT_R5.md`: external r5 construct audit; all 18 historical suites were judged formally present but construct-invalid.
- `docs/FINAL_SCIENTIFIC_ACCEPTANCE_AUDIT.md`: historical r5 remediation report; not the current scientific acceptance decision.
- `docs/T311_CONSTRUCT_VERTICAL_SLICE_ACCEPTANCE.md`, `docs/ADR_CONSTRUCT_REMEDIATION_T311.md`: T311 remediation design.

## Contracts and data
- `contracts/schema/construct.schema.json`: schema for all construct contracts.
- `contracts/constructs/T311.json` through `T363.json`: 18 versioned, schema-valid contracts. Their `implementation_status` fields are repository governance metadata; scientific status must be read with the runtime, baseline, counterfactual and replay evidence below.
- `src/ioabench/data_generation/`, `docs/09_DATA_GENERATION_AND_DATASET_LIFECYCLE.md`: generation and freeze framework.
- `data/datasets/DATASET_PACK_v4.yaml`: the frozen authoritative Benchmark Dataset Pack (18 suites); v1/v2 remain as historical provenance.

## T311 evidence
- `src/ioabench/suites/t311/construct_scoring.py`: causal scorer using actions, delegation, state and hidden Oracle join.
- `src/ioabench/replay/construct_audit.py`: replay integrity checks.
- `tests/construct/test_t311_construct.py`: 24 offline construct tests.
- `data/datasets/T311-dev-mini/`: development fixture data; not a formal new dataset.

## Historical runs and artifacts
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/`: historical 1620-case r5 run; preserve for audit, do not interpret as final construct-valid evidence.
- `data/runs/` and `artifacts/runs/`: all retained historical runs, mock runs and replay artifacts.
- `artifacts/gates/`, `artifacts/audits/`, `data/reports/`: historical gates, audits and reports.
- `release/BENCHMARK_RELEASE_v3-20260930.json` + `release/MODEL_PROFILE_deepseek-v4.1-flash.json`: the frozen Benchmark Release and tested-model profile.

## Tests and reproducibility
- `tests/`: offline unit, contract, construct, replay, scorer, baseline, and historical gate tests.
- `scripts/validate_spec.py` or `python -m ioabench.cli validate-spec`: offline schema/spec validation.
- `artifacts/handoff/HANDOFF_BUNDLE_MANIFEST.json`: external companion manifest for the ZIP hash, CRC, exclusions and secret scan.

## Known boundary
This snapshot does not call AIHubMix, generate datasets, or modify historical runs, gates or frozen datasets. It packages the completed benchmark: frozen Benchmark Release v3-20260930, the completed deepseek-v4.1-flash campaign (18x90/90 terminal, `artifacts/gates/ONLINE_CAMPAIGN_STATE.json`), G2 independent validation (`artifacts/gates/INDEPENDENT_SEMANTIC_VALIDATION.json`), replay audit (`artifacts/gates/REPLAY_AUDIT_V3.json`), Phase C results and dashboard (`artifacts/gates/PHASE_C_CAMPAIGN.json`, `artifacts/reports/`), and the final scientific acceptance (`artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`, verdict PASS).
