# ADR-V5-001 — Supplied-case execution and evidence closure

Date:2026-10-12. Status:implemented; authority:PI-V5-009. Builds on ADR-V5-000.

The18-suite frozen registry and original runner cannot load the opt-in dynamic IDs. Individual adapters already execute, but there was no common supplied-data path through batch persistence, safe reentry, ordered replay and engineering reports. Replacing the frozen registry or formal Pilot would mix implementation verification with confirmatory protocol changes.

Add an exact opt-in dynamic registry and a thin engineering entry in `v5/evaluation.py`, using the existing classic/dynamic runners, core engine, AttemptJournal, exposure/outcome definitions and statistics. `scripts/v5/evaluate.py` exposes run/report/replay; no data generation or formal-data freeze occurs here. Engineering evidence remains explicitly ENGINEERING_REFERENCE or ENGINEERING_SMOKE.

Pin source, supplied cases, ModelProfile, request parameters and exact provider identity before case execution. Bind chronological responses to complete requests including agent role. Use per-run OS locking, atomic input/checkpoint writes and flushed append-only evidence. Existing terminal rows are skipped; after any retained response an interrupted case is not re-executed. Preserve an interrupted tail in place and start a new result segment. Historical run-ID collisions and changed manifests fail closed.

AIHubMix identifies actual billing/serving identity in X-Aihubmix-Model. Body names can vary between the exact returned snapshot and catalog alias. Evaluation1.0.1 freezes those two observed/configured strings before execution; unexpected body or gateway identities are retained and rejected before their proposed actions execute. This is an engineering correction, not tested-model substitution or a change to frozen formal manifests.

Export independent safety, utility, recovery, exposure/missingness and family-paired statistics with evidence indices. Monitoring uncertainty and scorer abstention remain outside valid behavioral denominators. Review export accepts dynamic structures but keeps the canonical18 grouping and explicit sample shortfalls. Review disagreements remain human decisions; AI labels never pass Gate D.

Validation:472 tests;3240 offline checks;74 supplied cases ×2 policies/148 exact replays; fresh two-case real DeepSeek multiround run/ordered replay and zero-call resume. Scope is the existing37 adapters. Arbitrary-world compilation, qualified generated datasets, human review and formal research remain outside this decision. Exact source archives preserve both identity-check versions.
