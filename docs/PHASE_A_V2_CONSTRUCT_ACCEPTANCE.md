# Phase A V2 — Construct Implementation Acceptance

- Status: **PASS with one documented deviation** (2026-09-28)
- Gate artifact: `artifacts/gates/PHASE_A_V2_FINAL_ACCEPTANCE.json` (`overall_pass=true`)
- Verifier: `scripts/verify_phase_a_v2_gate.py` (re-runnable)
- Source hash at acceptance: `001db1cf4aa127ed2fa7ff3a28f8d8d620463e264f36e5c7c16b15bf90c3b717`
- Incident: `artifacts/gates/INCIDENT_SUITE_GATES_T311_20260928.json` / `docs/ADR_PHASE_A_V2_INCIDENT_SUITE_GATES_T311.md`

## What Phase A V2 closed

Phase A was reopened (`ADR_PHASE_A_V2_REOPEN.md`) because the previous offline
gate certified suites whose mechanism and difficulty variants generated
identical causal worlds. This acceptance closes the reopened phase:

1. **Mechanism causal diversity, 18/18.** Every suite generator produces five
   mechanism-specific payloads over a fixed seed, and the hidden truth carries
   the mechanism-specific unsafe consequence and recovery path where the truth
   is verdict-shaped. Verified live by `verify_phase_a_v2_gate.py` and frozen
   by the per-suite causal test battery.
2. **Difficulty causal diversity, 18/18.** Easy/Medium/Hard change real
   construct difficulty (delegation hops, propagation depth, episode counts,
   candidate counts, distractors, conflicting endorsements, verification
   workload) with passing `DifficultyCalibrator` classification.
3. **Contract conformance, 18/18.** `artifacts/gates/CONSTRUCT_CONFORMANCE_V2.json`
   validates every `contracts/constructs/Txxx.json` field through execution:
   roles, tested-agent minimums, scripted environment actors, environment
   state, model-visible evidence, contract verbs, state transitions,
   safe/unsafe/recovery conditions, utility separation, required raw metrics
   (canonical names published by every scorer), interaction depth, replay
   immutability, forbidden-shortcut scans, and SIMULATION_ONLY labeling.
4. **Specialized causal runtimes, 18/18.** Each suite executes through a
   versioned runtime consuming the generated/frozen world (e.g.
   `delegation-chain-2.0.0`, `propagation-network-2.0.0`,
   `longitudinal-norm-2.0.0`, `{suite}-incentive-reputation-2.0.0`,
   `{suite}-agency-2.0.0`, `T353-selection-2.0.0`, `T311` construct runtime);
   legacy fixtures remain on legacy paths for historical replay.
5. **Unified formal dispatcher.** `run --suite Txxx` and `--suite all` execute
   frozen cases directly through `construct_dispatch.py` (no regeneration, no
   legacy `execute_mock_case` in the formal path); results carry dispatch and
   runtime versions; checkpoint/resume remain manifest-bound.
6. **Causal test battery.** 13 dedicated files assert per-suite safe/naive/
   alternative/recovery baselines, causal and Oracle-only counterfactuals,
   state-causality (suppressed writes), Oracle/SUT isolation, context
   isolation, interaction depth, invalid-model-output handling, replay
   immutability/tamper detection and scorer recalculation. High-risk suites
   carry structural assertions (delegation chains with per-hop model sessions,
   per-hop propagation autonomy, four-role private-evidence deliberation,
   T352 feedback loop, T353 paired honest/manipulated worlds, T361–T363
   scripted-persona structure with personas never invoking the model).
7. **T311 regression.** The original vertical-slice suite passes together with
   the new causal-diversity battery.
8. **Windows clean offline regression.** 802 passed, 2 integration tests
   deselected, in the isolated workspace
   (`artifacts/gates/V2_A00_BASELINE/pytest-after-dispatcher.xml`), reproduced
   end-to-end including the conformance verifier.
9. **Historical integrity.** 16,413 of 16,414 protected files byte-identical.
   The single exception is documented below.

## Documented deviation

`artifacts/suite-gates/T311.json` (a superseded mock-era gate badge, not a
dataset/run/oracle/scorer artifact) was overwritten by the gate verification
run itself. Byte-exact recovery is impossible (replay hashes embed
wall-clock timestamps) and no pre-overwrite snapshot exists. The incident,
recovery attempts and impact assessment are recorded in
`INCIDENT_SUITE_GATES_T311_20260928.json` and
`ADR_PHASE_A_V2_INCIDENT_SUITE_GATES_T311.md`. The acceptance verdict carries
this exception explicitly; nothing was silently absorbed.

## What this acceptance does NOT claim

- No formal per-suite datasets are frozen under the V2 recipes yet (Phase B).
- No online model evaluation has been performed in this recovery
  (provider_calls = 0 throughout).
- T361–T363 remain SIMULATION_ONLY with synthetic personas; no real-human
  inference is claimed anywhere.
- The T311 2.0.0 dataset and its earlier online pilot remain
  provisional/exploratory pending the Phase B audit (B4).

## Next

Phase B per-suite lifecycle (T311 first): `TRIAL_GENERATION` →
`RECIPE_VALIDATED` → `FORMAL_DATASET_FROZEN` → `ONLINE_PILOT` →
`ONLINE_PILOT_PASS` → `FORMAL_RUN` → `FORMAL_EVALUATION_COMPLETE`, then Phase C
campaign aggregation and the final scientific acceptance.
