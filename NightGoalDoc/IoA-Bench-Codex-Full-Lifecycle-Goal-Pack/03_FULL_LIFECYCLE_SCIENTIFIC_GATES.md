# Full Lifecycle Scientific Gates

## Stage A — Code/Construct Gates

A0 taxonomy unchanged
A1 18 construct contracts valid
A2 18 runtimes construct-specific
A3 raw evidence / Oracle isolation
A4 safe baseline
A5 unsafe baseline
A6 state causality
A7 scorer counterfactual
A8 Replay immutable timing
A9 multi-agent minimum roles
A10 longitudinal structure where required
A11 Task Utility separated
A12 T311 regression
A13 no generic event shortcut
A14 offline tests
A15 historical artifact protection

Phase A cannot close unless 18/18 pass.

---

## Stage B — Trial Generation Gates (per suite)

B0 Runtime version frozen for trial
B1 small trial candidate set generated
B2 Ground Truth programmatic
B3 schema pass
B4 construct conformance
B5 task solvability
B6 safe path
B7 unsafe path
B8 raw evidence no verdict leakage
B9 semantic validation
B10 dedup
B11 difficulty signal
B12 mechanism/world coverage
B13 runtime dry-run
B14 scorer/utility sanity
B15 Replay sample audit
B16 rejection analysis complete

Only then `GENERATION_RECIPE_VALIDATED`.

---

## Stage C — Formal Dataset Gates (per suite)

C0 recipe version frozen
C1 overgenerated candidate pool
C2 quality threshold unchanged
C3 enough qualified cases
C4 target ~90
C5 Easy/Medium/Hard ~30 each
C6 Control/Risk valid
C7 validators/arbitration recorded
C8 provenance complete
C9 rejected set retained
C10 cases hash
C11 manifest hash
C12 immutable freeze

Only then `FORMAL_DATASET_FROZEN`.

---

## Stage D — Online Pilot Gates (per suite)

D0 exact tested model ID resolved
D1 provider credentials available only in env
D2 model/profile/prompt/tool/budget frozen
D3 pilot Run Manifest frozen
D4 representative cases selected
D5 non-empty valid Agent interactions
D6 tool/A2A/state transitions correct
D7 Oracle never visible
D8 scorer reconstructs from Replay
D9 Task Utility meaningful
D10 cost/latency captured
D11 provider errors separated
D12 no construct failure discovered

Only then `ONLINE_PILOT_PASS`.

---

## Stage E — Formal Suite Run Gates

E0 new independent formal run ID
E1 exact frozen dataset
E2 exact frozen runtime/scorer/prompt/model
E3 checkpoint/resume
E4 all work units terminal
E5 no silent model switch
E6 infra failures not scored against model
E7 Replay complete
E8 Replay audit pass
E9 scorer recalculation pass
E10 result integrity
E11 metrics/report
E12 representative failure extraction
E13 suite scientific acceptance

Only then `FORMAL_EVALUATION_COMPLETE`.

---

## Stage F — Final Campaign Gates

F0 18/18 formal suite complete
F1 campaign manifest
F2 exact model profile compatibility
F3 dataset manifests 18/18
F4 runtime/scorer versions 18/18
F5 no incompatible result mixing
F6 18 detailed results
F7 six-category profile
F8 Safety/Utility separate
F9 SIMULATION_ONLY labels
F10 limitations
F11 Dashboard
F12 representative failures
F13 full replay audit
F14 reproducibility bundle
F15 secret scan
F16 Windows reproducibility
F17 Linux status explicitly PASS or NOT VERIFIED
F18 final scientific audit PASS
F19 final project state complete
