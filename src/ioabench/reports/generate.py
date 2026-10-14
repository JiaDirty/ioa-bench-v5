"""Evidence-linked Markdown report generation."""

from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any


_CATEGORIES = {
    "trust_authorization": ("T311", "T312", "T313"),
    "protocol_interop": ("T321", "T322", "T323"),
    "propagation_inference": ("T331", "T332", "T333"),
    "public_knowledge": ("T341", "T342", "T343"),
    "ecosystem_power": ("T351", "T352", "T353"),
    "human_agency_simulation": ("T361", "T362", "T363"),
}


def generate_report(summary: dict[str, Any], output: str | Path, *, model_id: str, provider_status: str = "NOT_RUN") -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# IoA-Bench v1 Research Report", "", f"- Tested model: `{model_id}`", f"- Provider status: `{provider_status}`", "- Safety and Task Utility are reported separately.", "- No overall 18-suite safety score is reported.", ""]
    lines.append("## Validity")
    lines.append(f"- Run status counts: `{json.dumps(summary.get('status_counts', {}), sort_keys=True)}`")
    lines.append("\n## Suite Results")
    lines.append("| Suite | Cases | Valid | Task success | Estimated cost (USD) | Validity |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for suite, value in summary.get("suites", {}).items():
        lines.append(f"| {suite} | {value['case_count']} | {value['valid_count']} | {value['task_utility']['task_success']} | {value.get('cost', {}).get('usd')} | {value['validity']} |")
    lines.extend(["", "## Limitations", "- Results describe this frozen synthetic benchmark run only.", "- T361–T363 are `SIMULATION_ONLY`; they use synthetic personas and do not support real-human population inference.", "- Provider failures, unsupported cases and invalid runs are excluded from behavioral safety denominators.", "- One repetition per frozen case does not estimate within-case stochastic variance.", "- Token usage and end-to-end model timing come from replay evidence; cost is a current AIHubMix catalog estimate, not a historical invoice.", "", "## Evidence", "- Machine-readable metrics: `metrics/summary.json`.", "- Tabular export: `tables/suite-metrics.csv`.", "- Representative replay links: `case-studies/selected.json`.", ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    tables_dir = output.parent / "tables"
    figures_dir = output.parent / "figures"
    tables_dir.mkdir(exist_ok=True)
    figures_dir.mkdir(exist_ok=True)
    with (tables_dir / "suite-metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("suite", "case_count", "valid_count", "invalid_count", "task_success", "estimated_cost_usd", "validity", "safety_metrics"))
        writer.writeheader()
        for suite, value in summary.get("suites", {}).items():
            writer.writerow({"suite": suite, "case_count": value["case_count"], "valid_count": value["valid_count"], "invalid_count": value.get("invalid_count", value["case_count"] - value["valid_count"]), "task_success": value["task_utility"]["task_success"], "estimated_cost_usd": value.get("cost", {}).get("usd"), "validity": value["validity"], "safety_metrics": json.dumps(value.get("safety_metrics", {}), sort_keys=True)})
    (tables_dir / "suite-metrics.json").write_text(json.dumps(summary.get("suites", {}), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    risk_profile = {
        "run_id": summary.get("run_id"),
        "tested_model": model_id,
        "overall_safety_score": None,
        "pricing": summary.get("pricing"),
        "categories": {category: {suite: summary.get("suites", {}).get(suite) for suite in suites} for category, suites in _CATEGORIES.items()},
        "limitations": ["Frozen synthetic benchmark only", "T361-T363 are SIMULATION_ONLY", "No real-human or general-population inference"],
    }
    (output.parent / "risk-profile.json").write_text(json.dumps(risk_profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bars = []
    for index, (suite, value) in enumerate(summary.get("suites", {}).items()):
        utility = value["task_utility"].get("task_success")
        if utility is None:
            continue
        bars.append(f"<text x='8' y='{22 + index * 18}'>{suite}</text><rect x='48' y='{10 + index * 18}' width='{max(0.0, min(1.0, float(utility))) * 240:.2f}' height='12' fill='#2563eb'/>")
    (figures_dir / "task-utility-by-suite.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' width='300' height='" + str(max(30, 20 + len(bars) * 18)) + "' viewBox='0 0 300 " + str(max(30, 20 + len(bars) * 18)) + "'><text x='8' y='12'>Task Utility (separate from safety)</text>" + "".join(bars) + "</svg>\n", encoding="utf-8")
    return output
