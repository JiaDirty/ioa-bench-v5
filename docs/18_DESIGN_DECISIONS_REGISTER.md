# 18 — Confirmed Design Decisions Register

This register summarizes the user-confirmed design tree. `state/DESIGN_DECISIONS.yaml` contains the machine-readable Q001–Q132 mapping.

## Core purpose
- Research prototype first, not a production service.
- Score model endogenous safety in IoA scenarios; do not score the reference IoA infrastructure itself.
- Initial tested model: `deepseek-v4.1-flash` through AIHubMix.
- Future architecture must permit fair same-benchmark cross-model comparison.

## Data
- 18 independent datasets; one shared automated generation framework.
- No required manual authoring/review in the formal data-production loop.
- Program determines truth/structure; AIHubMix enriches language/content.
- Independent AI validation; additional validators for semantically complex cases.
- Freeze datasets; no in-place edits.
- ~90 qualified cases/suite; Easy/Medium/Hard ~30/30/30; generate surplus candidates.
- 4–6 mechanism templates/suite, instantiated across multiple shared synthetic worlds.
- If quotas fail, improve the pipeline; never lower quality gates.

## Agents/runtime
- Same tested model may back all participating normal agents; each has independent context/memory and role-specific prompt.
- Environment-only actors are scripted where cognition is irrelevant.
- Standard adversaries scripted; autonomous attacker model is a separate extension.
- Agents may autonomously plan, discover, verify, delegate, call tools, refuse and recover within budgets.
- No public Internet in formal runs; real state changes occur only inside synthetic sandbox services.

## Measurement
- Observable behavior over prose; rule-based scoring over AI judging.
- Exposure proof required.
- Safety and task utility reported separately.
- Common stage model: Exposure, Recognition, Verification, Decision, Action, Recovery.
- Partial safety/recovery states are preserved; no binary-only reduction.
- Per-suite composite allowed with transparent raw metrics; no mandatory one-number overall score.
- Full replay mandatory.

## Human-agency suites
- v1 uses synthetic personas for T361–T363.
- Results are `SIMULATION_ONLY` and cannot be generalized to real humans.

## Operations
- v1 runs directly on local computer; Docker not required.
- AIHubMix is the sole v1 model gateway behind `ModelPort`.
- One-command all-suite execution, checkpoint/resume, automatic dashboard/reporting.
- Codex highly autonomous for engineering, but cannot change canonical risks, research objective, frozen data or core scoring meaning without human approval/versioning.
