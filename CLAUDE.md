# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

`AGENTS.md` is normative and overrides everything else. It defines the frozen 18-risk taxonomy (T311–T363), the model-centric research objective, and the non-negotiable scientific boundaries. Before any implementation work also read `state/PROJECT_STATE.yaml` and `state/WORK_QUEUE.yaml` (an executable task DAG; pick the highest-priority unblocked item, never skip dependencies). After a task, update queue status, project state, and changelog/ADR as `AGENTS.md` §13 requires.

When artifacts conflict, precedence is: `AGENTS.md` → `contracts/schema` + `contracts/ddl/sqlite` → `contracts/python/*.pyi` → numbered `docs/NN_*.md` → examples/templates. `README.md` gives the full doc read order.

## Commands

Python ≥3.12, package in `src/ioabench` (setuptools, `pip install -e .[dev]`). The host is Windows; run shell commands from Git Bash.

```bash
python -m pytest -m "not integration"            # offline suite, no credentials needed
python -m pytest tests/t311/test_x.py::test_name # single test
python -m pytest -m integration                  # live AIHubMix checks; needs AIHUBMIX_API_KEY
ruff check src tests scripts
mypy                                             # strict, configured in pyproject.toml

ioabench validate-spec                           # validate shipped schemas/examples
ioabench status                                  # project state + ready work
ioabench construct-baseline --suite T311 --policy safe|naive|alternative|recovery
ioabench dataset generate|validate|freeze --suite T3xx ...
ioabench run --model deepseek-v4.1-flash --suite all [--resume --run-id ...]
ioabench run-validate|analyze|report|replay-audit|dashboard --run <run_id>
```

If `ioabench` is not installed, use `PYTHONPATH=src python -m ioabench.cli ...`. Pytest already adds `src` to the path through `pyproject.toml`.

Test conventions: the `integration` marker covers anything that touches a real provider. When you fix a bug, add a regression test named `test_regression_<bug>`. Shared fixtures (`local_stores`, `deterministic_world`) are in `tests/conftest.py`.

## Architecture

**Formal execution path.** A frozen case goes through `runtime/construct_dispatch.py`: frozen case → suite adapter (`build_*_case_from_skeleton`) → suite causal runtime (`execute_*`) → tested agents → synthetic state → oracle join on the evaluator side only → causal scorer → replay bundle. The `RUNNERS` map links each suite to its runtime module in `src/ioabench/runtime/`. Several suites share one runtime (for example T321/T322 use `protocol_state_machine`, T313/T323 use `delegation_provenance`). `runtime/offline_run.py` is the **legacy generic path** (`read_case → query_source_record → complete_task`). An audit found it construct-invalid, so it is kept only to replay historical runs. Don't route new formal work through it.

**Per-suite packages** (`src/ioabench/suites/tXXX/`) each have `spec.py`, `generation.py` (Generator + WORLDS), `scenario.py`, `validators.py`, `scoring.py`, and `construct_scoring.py`. T361–T363 also have `persona_runtime.py` and must always be labelled `SIMULATION_ONLY`. Shared world builders live in `suites/_*.py`. Each suite has a versioned construct obligation in `contracts/constructs/T*.json`.

**Frozen versions.** `src/ioabench/frozen_versions.py` is the single source of truth for which dataset version each suite uses (`data/datasets/<suite>/<version>/{cases.jsonl,manifest.json}`). Import it; never copy the map (a duplicated map has already caused incidents). Frozen datasets are immutable. A fix means a new version.

**Models.** All model calls go through `ModelPort` (`models/base.py`). The implementations are `models/aihubmix.py` (live; the key comes from env `AIHUBMIX_API_KEY` / `.env`), `models/mock.py` (offline tests and baselines), and `models/replay.py`. The tested model profile is `config/models/deepseek-v4.1-flash.yaml`. Generation and semantic-validation models are configured separately (`generation/model_router.py`) and must stay distinct from the tested model in provenance.

**Storage isolation.** `storage/sqlite/stores.py` `LocalStores` manages four separate SQLite files (control, sut, oracle, telemetry), with DDL in `contracts/ddl/sqlite/`. Tested-agent processes must never get oracle paths or handles; `security/isolation.py` and `tests/isolation/` enforce this.

**Reference IoA scaffold.** `ioa/` (registry, identity, authorization, delegation, router, reputation, knowledge, incentive, memory), `protocols/a2a` and `protocols/mcp` adapters, and `sandbox/` (synthetic local services and action budgets). These are experimental stimuli, not the object being scored.

**Generation pipeline.** `generation/`: skeleton + programmatic truth → AI naturalization → deterministic validators → semantic validation/arbitration → repair → dedup → leakage → difficulty → coverage → freeze. Rejected candidates and their reasons are kept in provenance.

**Releases and campaigns.** The release lineage is in `release/BENCHMARK_RELEASE_*.json`. Formal campaigns run through version-stamped script families in `scripts/` (e.g. `run_online_campaign_v4_1_13.py`, `v4_1_13_{live_smoke,freeze_release,freeze_run_manifests,validate_run,strict_binding_audit,finalize_campaign}.py`). Each script binds to its own release file and keeps its state under `artifacts/scientific_closure_v4/`. New corrective versions have so far been added as new script sets rather than by editing older ones, which keeps historical runs reproducible. Run outputs go to `data/runs/`; gates, audits, and reports go to `artifacts/`.

## Things to avoid

- Don't put risk IDs, intended safe answers, or oracle labels in tested-agent prompts.
- Don't tune frozen tested-agent prompts against observed results.
- Don't lower dataset quality gates to fill quotas.
- Don't change scorer semantics after results exist without bumping the version and re-running.
- The root `*.zip` files, `NightGoalDoc/`, and `exports/` are handoff/goal-pack archives, not source. Don't search or edit them.
