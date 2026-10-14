# 14 — Codex Autonomous Execution Playbook

## 1. Startup ritual

Every Codex session:
1. inspect repository status;
2. read `AGENTS.md`;
3. read `state/PROJECT_STATE.yaml`;
4. read `state/WORK_QUEUE.yaml`;
5. select the highest-priority unblocked task;
6. read referenced contracts/docs/tests;
7. implement the smallest complete vertical slice;
8. run acceptance commands;
9. add regression tests for bugs;
10. update state/work queue/changelog/ADR as required.

## 2. Autonomy levels

### Autonomous
Implementation details, refactoring behind contracts, tests, local performance, retry handling, generation-prompt improvements before freeze, bug fixes, documentation consistency.

### ADR then autonomous
Non-core storage/runtime swaps, adapter replacement, new optional dependency, material schema extension, dashboard redesign, changed generation architecture.

### Human approval required
Change to any of the 18 meanings; model-centric objective; formal dataset mutation; formal tested-agent prompt after freeze based on results; scoring construct redefinition; real-human study claim; deletion of Oracle separation.

## 3. Blocker policy

Do not ask the user to make technical choices that can be resolved by evidence/engineering judgment. Search docs, inspect APIs, prototype, test, then choose and record rationale.

Stop and request human input only when the unresolved choice changes research meaning, cost/risk commitment outside configured limits, ethics/human-study scope, or a frozen benchmark contract.

## 4. Data-generation self-improvement

If quality quota is not met, Codex must analyze rejection reasons and iteratively improve mechanism constraints, prompts, model routing, repair policy, validators or difficulty calibration. It must never solve quota by lowering the frozen quality standard.

## 5. “Done” discipline

A work item is done only when code, tests, docs/contracts, acceptance command and state update are complete. “Implemented but not tested” remains in progress.

## 6. No benchmark gaming

Codex must not inspect model failures and then inject risk-specific warnings into the formal base prompt. It may fix benchmark bugs and regenerate/version datasets, but must preserve construct validity.
