# IoA-Bench — Codex Master Instructions

> **Status:** normative. Codex MUST read this file before any implementation work.  
> **Spec version:** 1.0-draft-model-centric  
> **Purpose:** evaluate **a model's endogenous safety behavior in IoA scenarios**, not the security of the reference IoA infrastructure.

## 1. Mission

Build **IoA-Bench**, a local-first, reproducible benchmark that places a tested foundation model into a controlled Internet-of-Agents (IoA) environment, instantiates that model as multiple role-separated agents, exposes those agents to 18 canonical IoA risk mechanisms, and measures the model's observable safety behavior across **Exposure → Recognition → Verification → Decision → Action → Recovery**.

The reference IoA environment is an **experimental scaffold**. Infrastructure faults, misleading registry records, protocol ambiguities, malicious peers, topology patterns, reputation signals and incentive signals are stimuli. They MUST NOT be scored as model failures unless the tested model observes/responds to the stimulus and exhibits unsafe behavior under the scenario's causal rules.

## 2. Canonical taxonomy — frozen

The following 18 risks are normative and MUST NOT be renamed, merged, deleted, split, or semantically redefined by Codex:

### 3.1 信任与授权失灵
- T311 资格伪装 / Qualification Spoofing
- T312 注册失真 / Registry Distortion
- T313 代表资格漂移 / Representation/Delegation Drift

### 3.2 协议互操作失配
- T321 协商污染 / Negotiation Pollution
- T322 互操作失配 / Interoperability Mismatch
- T323 责任链断裂 / Accountability Chain Break

### 3.3 互联扩散与可推断性
- T331 跨系统级联扩散 / Cross-System Cascade
- T332 结构暴露 / Structural Exposure
- T333 行为推断 / Behavioral Inference

### 3.4 公共知识失真
- T341 生态错误共识 / Ecosystem False Consensus
- T342 谣言扩散 / Rumor Propagation
- T343 规范漂移 / Norm Drift

### 3.5 生态权力失衡
- T351 激励错配 / Incentive Misalignment
- T352 声誉垄断 / Reputation Monopoly
- T353 节点操纵 / Node Manipulation

### 3.6 人机能动性侵蚀
- T361 判断让渡 / Judgment Delegation
- T362 讨论扭曲 / Discussion Distortion
- T363 能动性弱化 / Agency Weakening

## 3. What is being evaluated

### 3.1 Tested object
The scored object is a **model configuration**, initially `deepseek-v4.1-flash`, accessed through `ModelPort` and the AIHubMix adapter.

A benchmark run MAY instantiate the same tested model as multiple normal agents. Each tested agent MUST have an independent context, independent memory, role-specific system prompt, identity, organization, capability set and permissions. Agents MAY exchange information only through explicit IoA channels and shared resources exposed by the scenario.

### 3.2 What is not being evaluated
The default benchmark does NOT claim to evaluate:
- AGNTCY, A2A, MCP, OpenFGA or any infrastructure implementation as a security product;
- whether the reference Registry/Router/Gateway is production-safe;
- real human agency for T361–T363 in v1;
- real-world truth outside the synthetic benchmark worlds.

## 4. Non-negotiable scientific boundaries

1. **Model-centric causality.** A scenario condition is only an exposure until the tested model receives or can act on it.
2. **Ground truth is external.** Tested agents MUST never access Oracle truth labels, scoring rules or hidden attack labels.
3. **No benchmark leakage.** Prompts MUST NOT tell the model which of the 18 risks is being tested or provide the intended safe answer.
4. **No post-hoc prompt tuning.** After a frozen benchmark is evaluated, Codex MUST NOT modify the tested-agent base prompt to improve scores on those cases.
5. **Safety and utility are separate.** Refusing everything is not high safety. Report safety behavior and task utility independently.
6. **Observable behavior first.** Prefer actions, verification calls, delegation choices, tool calls, forwarding behavior and recovery steps over final prose.
7. **Rules before judges.** Deterministic scoring rules take precedence. AI judges MAY classify semantic evidence only where deterministic rules are insufficient.
8. **Frozen datasets are immutable.** Fixes create new dataset/scenario/scorer versions; they never silently mutate released data.
9. **No lowering quality gates.** If generation cannot produce enough qualified data, improve generation/validation strategy; do not weaken thresholds to fill quotas.
10. **Full replay.** Every formal case MUST be reconstructable from persisted inputs, events, model I/O, actions, injected stimuli, scoring evidence and version manifests.

## 5. v1 benchmark profile

- Host: one local computer; Windows-compatible.
- Docker: NOT required for v1.
- Model provider: AIHubMix only in v1, hidden behind `ModelPort`.
- Tested model: `deepseek-v4.1-flash` after live model-ID validation at run freeze.
- Modalities: text + structured data for v1.
- Internet: tested agents MUST NOT access the public Internet during formal runs.
- Business resources: synthetic local Sandbox services only.
- Scale: small IoA; typically 2–3 organizations and 4–10 tested agents depending on suite.
- Repetitions: default 1 for v1; configurable for later studies.
- Dataset target: ~90 qualified formal cases per Txxx suite, normally ~30 Easy / 30 Medium / 30 Hard.
- Data creation: automated only; no required manual authoring or review gate.
- T361–T363: implemented with synthetic personas and MUST be labeled `SIMULATION_ONLY`.

## 6. Reference IoA architecture rule

The reference IoA SHOULD use real protocol semantics where practical (A2A for agent↔agent; MCP for agent↔tool), while benchmark-specific Registry, Identity, Delegation, Router, Reputation, Knowledge and Sandbox services SHOULD be lightweight, deterministic and controllable. AGNTCY integrations are optional integration profiles, not mandatory v1 runtime dependencies.

Third-party SDKs MUST remain behind adapters.

## 7. Model/provider rules

All model calls MUST go through `ModelPort`.

`AIHubMixAdapter` MUST:
- obtain `AIHUBMIX_API_KEY` from environment/secret storage only;
- use live model discovery/capability validation before freezing a run;
- persist exact model ID, endpoint family, parameters and relevant provider response metadata;
- retry bounded transient failures;
- NEVER silently substitute another tested model after a run manifest is frozen;
- separate generator, validator/judge and tested-model roles in provenance.

Candidate generation/validation models MAY include AIHubMix-available DeepSeek, GLM, Qwen, GPT, Claude and Gemini models. Do not hardcode a stale global list as truth.

## 8. Agent rules

Normal participating IoA agents in the formal benchmark SHOULD use the tested model. Environment-only roles (fixed services, scripted feedback sources, deterministic helper actors) SHOULD be scripted where cognition is irrelevant.

Standard malicious/adversarial peers MUST be scripted/replayable. Autonomous attacker-model mode is an `Adversarial Extension` and MUST NOT be mixed into the canonical score.

Each tested agent MUST:
- have a role-specific neutral system prompt;
- have independent model context and memory;
- see only information allowed by its scenario role;
- be able to plan multi-step actions within an explicit action budget;
- be allowed to verify, challenge, request clarification, query evidence, refuse, recover and complete the task safely.

## 9. Data-generation rules

There are **18 independent dataset suites** sharing one generation framework.

Each formal dataset MUST be generated from versioned mechanism templates, synthetic-world definitions and programmatic Ground Truth. AI models enrich natural language, roles, evidence, messages and distractors; they MUST NOT be the sole authority defining truth.

Each candidate goes through:
`template/ground-truth construction -> generation -> schema checks -> invariant checks -> independent semantic validation -> optional second validator/arbitration -> dedup -> difficulty calibration -> leakage checks -> freeze`.

Rejected candidates and their rejection reasons MUST be retained in generation provenance.

## 10. Scenario and scoring rules

Every formal case MUST include:
- risk mechanism template id;
- synthetic world id;
- difficulty label;
- control/attack pairing where applicable;
- explicit Ground Truth;
- explicit exposure condition;
- task utility objective;
- action/tool budget;
- deterministic observable safe/unsafe criteria;
- semantic judge criteria only where needed;
- replay requirements.

Scoring SHOULD distinguish at least:
- `EARLY_SAFE`
- `LATE_RECOVERY`
- `UNSAFE_ACTION`
- `FULL_FAILURE`

Each Txxx MAY publish a composite Txxx safety indicator, but MUST also publish all raw metrics and formulae. No mandatory overall 18-risk single score exists.

## 11. Local-first storage separation

v1 MUST work without service containers. Use separate local stores/files for:
- control/experiment state;
- SUT-visible state;
- Oracle hidden truth;
- telemetry/replay data;
- datasets;
- artifacts/reports.

Separate SQLite files are acceptable for control/SUT/oracle/telemetry in v1. Oracle credentials/paths MUST NOT be passed to tested-agent processes.

PostgreSQL/ClickHouse contracts MAY remain as scale-out profiles but MUST NOT be required for local v1.

## 12. Codex autonomy

Codex MAY autonomously:
- design non-core implementation details;
- add tests and regression tests;
- fix bugs;
- improve generation prompts/pipelines before dataset freeze;
- improve local runtime performance;
- change non-core architecture with an ADR;
- resume failed work from project state;
- run generation/evaluation/reporting.

Codex MUST NOT autonomously change:
- the 18 canonical meanings;
- the model-centric research objective;
- hidden-truth separation;
- frozen formal datasets;
- frozen formal tested-agent scaffolding;
- formal scorer semantics after results are generated without versioning/re-run;
- `SIMULATION_ONLY` status of synthetic-human results.

## 13. Required project-state discipline

Before work, Codex MUST read:
1. `AGENTS.md`
2. `state/PROJECT_STATE.yaml`
3. `state/WORK_QUEUE.yaml`
4. relevant contracts/docs.

After a task, Codex MUST update project state, tests, change log/ADR when required, and acceptance status. It MUST NOT claim a milestone complete unless its executable acceptance commands pass.

## 14. Definition of Done for v1

v1 is not done when code exists. It is done when:
- the local reference IoA launches without Docker;
- AIHubMix connectivity/model validation works;
- all 18 dataset generators exist;
- each suite has a frozen formal dataset target of ~90 qualified cases or an explicitly versioned generation blocker being actively resolved;
- all 18 suites execute end-to-end;
- `deepseek-v4.1-flash` completes the supported canonical run;
- T361–T363 are clearly `SIMULATION_ONLY`;
- scoring, utility metrics, replay, checkpoint/resume, dashboard and automatic research report work;
- one command can run `--suite all` against frozen versions;
- every reported number is traceable to evidence and a frozen Run Manifest.
