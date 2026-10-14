# 13 — Release, Reproducibility and Benchmark Governance

## 1. Versioned products

Version independently:
- runtime;
- suite/scenario pack;
- dataset pack per Txxx;
- mechanism templates;
- base agent scaffolding/prompts;
- scorers/judge rubrics;
- world/sandbox definitions;
- report schema.

A benchmark release manifest pins all compatible versions and content hashes.

## 2. Semantic changes

- Patch: defect fix that does not intentionally change construct/coverage, but affected formal results must be invalidated/re-run if outputs can change.
- Minor: additive mechanisms/worlds/metrics or meaningful generator/scorer changes.
- Major: construct/meaning-breaking change; requires human approval because canonical 18 meanings are frozen.

## 3. Dataset immutability

Frozen case content is immutable. A discovered ambiguous/incorrect case triggers a new dataset version; historical reports remain bound to the old version and may be marked superseded.

## 4. Run Manifest

Freeze before formal execution:
- tested model exact id/provider/protocol;
- sampling parameters;
- base prompt/scaffolding versions;
- suite/scenario/dataset hashes;
- world/sandbox versions;
- scorer/judge versions;
- code commit;
- dependency lock hash;
- OS/runtime info;
- concurrency/action-budget config;
- timestamp.

## 5. Bug impact analysis

When a benchmark bug is found, Codex must identify affected suites/cases/results, bump appropriate version(s), invalidate all affected formal results and rerun. Do not mix pre-fix and post-fix scoring logic in one final report.

## 6. ADR requirement

ADR required for changes to research construct, data-plane boundary, model/runtime abstraction, score semantics, dataset freeze rules, security isolation, major dependency strategy or autonomous-Codex policy.
