# 17 — Dashboard, Replay and Research Reporting

## 1. Local dashboard

v1 includes a local web dashboard with no cloud dependency. It must show:
- benchmark run status/checkpoints;
- 6 category / 18 suite overview;
- safety raw metrics and task utility side by side;
- difficulty/world/mechanism breakdowns;
- representative failure/recovery cases;
- model/provider usage and cost;
- invalid/unsupported/infrastructure failures separately.

## 2. Case replay

For one case, provide a chronological view:
world snapshot → agents/roles → exposure → messages → verification actions → model outputs → delegation/tool calls → sandbox state change → recovery → scorer evidence.

Do not expose Oracle truth to a live tested agent; replay is evaluator-only.

## 3. Research outputs

Automatically export:
- CSV/JSON raw and aggregate metrics;
- Markdown report;
- publication-ready tabular data (CSV and optional LaTeX table source);
- figures generated from frozen results;
- benchmark/run manifest;
- representative case-study bundles;
- limitations/validity section.

## 4. Narrative guardrail

Generated report text describes evidence, not unsupported generalization. T361–T363 prominently show `SIMULATION_ONLY`.
