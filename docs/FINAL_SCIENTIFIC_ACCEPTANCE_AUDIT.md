# IoA-Bench v1 Final Scientific Acceptance Audit

> Audit version: `v1.1-scientific-remediation`
>
> Scope: post-audit remediation of the historical engineering integration run
>
## 1. Acceptance Status

The historical `deepseek-v4.1-flash-v1` run is retained as an
`ENGINEERING_INTEGRATION_RUN` and is not a scientific benchmark result. Its
dataset versions were not the later M9 freeze, and its executor rebuilt a
generic skeleton instead of executing the frozen case payload.

The interrupted `deepseek-v4.1-flash-v1-pack-v2` run is retained as
`INVALID_FOR_SCIENTIFIC_BENCHMARK`. It was stopped after confirming that its
verification tool returned the complete visible case record. It must not be
resumed because doing so would mix pre-fix and post-fix runtime behavior.

The replacement formal run is:

- Run ID: `deepseek-v4.1-flash-v1-pack-v2-r5`
- Model: `deepseek-v4.1-flash`
- Provider: `aihubmix`
- Dataset pack: `DATASET_PACK_v2`
- Runtime: `scientific-runtime-4`
- Formal status: `PASS`
- Eligibility: `1620 VALID`, `0` infrastructure exclusions
- Outcome classes: `1502 EARLY_SAFE`, `83 UNSAFE_ACTION`, `35 FULL_FAILURE`

## 2. Remediation Implemented

### Frozen data and manifest

The replacement run freezes the dataset pack before scheduling any work. It
pins every suite version, content SHA-256, suite/scorer/base-prompt version,
exact model ID and runtime metadata in its immutable Run Manifest. The runtime
loads cases by `(suite, dataset_version, candidate_id)` from that manifest and
does not consult the current dataset-pack file after the manifest is frozen.

### Frozen case execution

The executor converts the persisted frozen case directly into the scenario
object and uses its `sut_payload` as the model-visible initial record. Replay
audit checks both the scenario payload and every model-visible `visible_record`
against the manifest-pinned frozen case.

### Independent source evidence

The MCP tool exposed to the tested model is the neutral
`query_source_record`. It reads a separate Sandbox source record, not the
`case_payload`. The source record is constructed per suite from the scenario's
independent local service state and returns risk-specific evidence such as
credential lookup status, directory suitability, delegation boundary,
protocol contract status, provenance completeness, claim support, reputation
quality, route independence or synthetic-persona context. The raw Oracle keys
and labels are not sent to the model.

### Multi-agent Reference IoA path

Every formal replay contains two independent `TESTED` agents and one scripted
peer. The execution path initializes and records Registry, Identity,
Delegation, Authorization, Router, Reputation, Knowledge, Incentive, A2A,
MCP and Sandbox state. Agent-to-agent messages and tool calls are persisted as
observable telemetry.

### Scorer discrimination and leakage

The naive baseline performs the unsafe action without querying the source
record and must produce `UNSAFE_ACTION` or `FULL_FAILURE` for all 18 suites.
The safe mock baseline must not be scored as unsafe. Formal dataset generation
also requires dual semantic validation and a passing tested-agent prompt
leakage gate. Existing frozen datasets are immutable; the v2 pack is a new
release and does not overwrite v1 content.

The final baseline gate passes all 18 suites. The formal model run contains
non-zero unsafe outcomes, so the result is not interpreted as universal safety
or as a scorer that labels every case safe.

## 3. Required Evidence Gates

The final gate is valid only when all of these artifacts agree on the same Run
ID and Manifest hash:

1. `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/manifest/`
2. `data/runs/deepseek-v4.1-flash-v1-pack-v2-r5/completeness.json`
3. `artifacts/runs/deepseek-v4.1-flash-v1-pack-v2-r5/replay-audit.json`
4. `data/reports/deepseek-v4.1-flash-v1-pack-v2-r5/metrics/summary.json`
5. `data/reports/deepseek-v4.1-flash-v1-pack-v2-r5/report.md`
6. `artifacts/gates/FINAL_SCIENTIFIC_ACCEPTANCE.json`

The recorded final results are:

| Gate | Result |
|---|---|
| Run validation | `VALID`, 1620/1620 records |
| Replay hash completeness | `1620/1620` |
| Frozen-case replay audit | `PASS`, 1620 audited, 0 failures |
| Dataset pack | `DATASET_PACK_V2`, 18 x 90, 30/30/30 |
| Naive baseline discrimination | 18/18 suites unsafe |
| Safe mock baseline | not unsafe |
| Simulation label | T361/T362/T363 all `SIMULATION_ONLY` |

The r5 analysis reports weighted Task Utility `53.40%`, `4885` model calls,
`4105` tool calls, `8,191,223` total tokens and an estimated `$1.112106609152`
from the dated AIHubMix catalog snapshot. Safety raw metrics remain per-suite;
these values are not collapsed into a single safety score.

The executable acceptance sequence is:

```powershell
$env:AIHUBMIX_API_KEY = "<process-only secret>"
python -m ioabench.cli run-validate --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m ioabench.cli replay-audit --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m ioabench.cli analyze --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m ioabench.cli report --run deepseek-v4.1-flash-v1-pack-v2-r5
python -m pytest -q
```

No API key is stored in this document, the run artifacts or the release
bundle.

## 4. Scientific Interpretation Rules

- Safety and Task Utility remain separate. Refusal or failed utility is not
  silently converted into a safety success.
- `EARLY_SAFE`, `LATE_RECOVERY`, `UNSAFE_ACTION` and `FULL_FAILURE` remain
  observable outcome classes; suite-specific raw metrics are retained.
- Infrastructure failures are excluded from model safety scoring and are
  reported as invalid, unsupported or retryable infrastructure outcomes.
- T361, T362 and T363 are `SIMULATION_ONLY` synthetic-persona results and do
  not support claims about real human agency.
- One repetition per frozen case remains a v1 limitation. It does not estimate
  model stochastic variance and should be expanded for comparative studies.
- A formal result is not accepted solely because all files exist: frozen-case
  equality, model-visible isolation, replay reconstruction and baseline
  discrimination are required.

## 5. Historical Artifacts

The following artifacts are intentionally retained for auditability:

- `data/runs/deepseek-v4.1-flash-v1/` — historical run, invalidated for the
  scientific benchmark after the external audit.
- `data/runs/deepseek-v4.1-flash-v1-pack-v2/` — interrupted pre-fix run,
  explicitly marked invalid and not resumable.
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r2/` — interrupted pre-scorer-fix
  run, explicitly marked invalid and not resumable.
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r3/` — interrupted pre-provider-
  async-fix run, explicitly marked invalid and not resumable.
- `data/runs/deepseek-v4.1-flash-v1-pack-v2-r4/` — completed run invalidated
  after Replay audit found the T312 scenario payload omission.
- `data/datasets/DATASET_PACK_v1.yaml` and its frozen suite directories —
  immutable historical data.
- `data/datasets/DATASET_PACK_v2.yaml` and its frozen suite directories —
  immutable replacement data used by the replacement run.

Historical results are never silently relabeled as replacement results.
