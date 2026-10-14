# ADR: T311 construct execution boundary

Date: 2026-09-25. Status: accepted for the offline T311 slice only.

## Context

The r5 construct gap audit found that the generic read/query/complete executor did not execute the 18 intended IoA mechanisms. The historical evidence, frozen Dataset Packs and gates are retained unchanged. A new formal paid run cannot legitimately reuse the r5 construct claim.

## Decision

1. Non-mock formal execution through the historical generic runner is blocked until a construct-specific frozen case can drive it. The old evidence service fails closed when an independent raw source record is absent; an Oracle-derived verdict is never synthesized for the tested model.
2. Versioned JSON construct contracts describe all 18 risks; only T311 has an executable implementation. Contracts document scientific obligations, not completion status for other suites.
3. T311 uses existing Registry, DelegationGraph/LocalAuthorizer, LocalA2AAdapter, SandboxCore, ModelPort, ReplayBundleBuilder and immutable manifest store. Model calls and evidence queries are independent of hidden Oracle truth; the evaluator joins Oracle after actions have completed.
4. The development fixture is not a formal frozen dataset. Its local, offline replay and source-tree revision hash establish a reference behavior for future dataset generation and model pilots, not a scientific model result. No r6 exists.
5. For simultaneous telemetry timestamps, Replay preserves event insertion order. A lexical event-ID tie break reordered e10 before e2 and broke causal action reconstruction.

## Consequences and next gate

T311 unsafe selection/delegation and actual invoice access are distinguishable from a harmless refusal or pre-effect revocation. The four offline policies exercise a single ModelPort boundary. Offline baselines prove scorer sensitivity, not real-model success. Before a paid formal run, publish a new T311 frozen dataset with independent raw evidence and validate a bounded online pilot after explicit approval; then implement and gate the other 17 mechanisms. T361–T363 remain SIMULATION_ONLY.
