# IoA-Bench v4 Corrective Changelog

This file records non-destructive successors to the frozen v4 corrective Release. Older Releases remain immutable historical evidence.

## v4.1.7 - 2026-10-02

- Preserve the v4.1.6 scientific source tree and correct the promotion audit scope so successor evidence files are not mistaken for executable-tree drift.
- Freeze the corrected audit and campaign tools, 18 new Release-bound Run Manifests, and a new Provider approval request. No Provider calls or Formal Runs occurred.

## v4.1.6 - 2026-10-02

- Retain every Synthetic Human internal Provider response in the append-only AttemptJournal, including malformed responses before a bounded protocol retry.
- Classify malformed tool-call output consistently as terminal `INVALID_MODEL_OUTPUT`; classify asynchronous cancellation through the strict infrastructure interruption rules.
- Bind each Run Manifest to the runtime version actually emitted in Replay, the suite contract hash, source tree, model profile, and frozen execution-tool hashes.
- Strengthen Phase F validation for exact attempt history, journal identity and hashes, retry legality, Replay integrity, tested-model identity, and Synthetic Human isolation.
- Strengthen final reporting and delivery inventory without changing taxonomy, Dataset, scorer, prompt, construct semantics, or tested-model roster.

## v4.1.2-v4.1.5 - 2026-10-02

Intermediate immutable successors used to close launch-path, runtime Manifest, execution-tool, campaign-completion, and state-version wiring defects found by offline fail-closed testing. They produced no Provider calls and no canonical Formal Runs.

## v4.1-v4.1.1 - 2026-10-02

Promoted the frozen corrective runtime into the workspace, separated v4 execution from historical Run IDs, and froze execution-tool hashes and 18 Release-bound Run Manifests.

## v4 corrective - 2026-10-01

Introduced strict retry semantics and the T353 paired-Replay corrective. Historical v3/v3.2 Runs remain historical evidence and are excluded from v4 canonical aggregation.
