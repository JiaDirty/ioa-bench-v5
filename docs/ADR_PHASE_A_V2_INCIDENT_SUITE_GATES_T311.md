# ADR: Incident — suite-gates/T311.json overwritten during Phase A V2 gate verification

- Status: accepted (2026-09-28)
- Incident record: `artifacts/gates/INCIDENT_SUITE_GATES_T311_20260928.json`
- Related: `ADR_PHASE_A_V2_REOPEN.md`, `artifacts/gates/V2_A00_BASELINE/inventory.json`

## Context

While assembling the Phase A V2 final acceptance gate, the gate script ran the
T311 regression battery in the main workspace and included
`tests/t311/test_e2e.py`. That test rewrites `artifacts/suite-gates/T311.json`
on every execution (this is the historical design of the mini-e2e gate: the
badge is rewritten, not appended). The rewrite hit a file pinned by the A00
baseline inventory.

## Decision

1. The overwrite is recorded as a formal incident with permanent provenance
   (`INCIDENT_SUITE_GATES_T311_20260928.json`) rather than silently absorbed
   into a re-baselined inventory.
2. The file is classified as a **superseded mock-era gate badge**, not a
   scientific asset: it is not a frozen dataset, frozen run, oracle artifact,
   or scorer evidence, and per `ADR_PHASE_A_V2_REOPEN` the old gates are
   superseded as current-acceptance evidence.
3. Byte-exact recovery is impossible: the replay bundle content hash embeds
   wall-clock timestamps (verified experimentally), and no pre-overwrite
   snapshot exists. The file now holds the 2026-09-27 12:35 deterministic-input
   regeneration (the newest recoverable state), recorded by hash in the
   incident record.
4. The Phase A V2 acceptance reports this exception **explicitly**: the raw
   `historical_artifacts_unchanged` evidence enumerates 16,413/16,414 intact
   plus this one incident; a separate reviewed-integrity condition records the
   impact assessment. The overall gate verdict names the exception.
5. Prevention: the gate script now excludes the e2e writer from main-workspace
   regressions (`--ignore=tests/t311/test_e2e.py`); full batteries including it
   run only in the isolated regression workspace; future gate scripts must
   assert they write nothing under protected paths before executing tests.

## Consequences

- The historical-integrity claim for Phase A V2 carries one documented
  exception out of 16,414 protected files; every other historical byte is
  verified unchanged.
- The inventory is NOT silently re-baselined. If a future decision re-baselines
  this entry, it must reference this ADR and the incident record.
- Gate scripts gained a write-audit obligation before executing test batteries.
