"""Phase C campaign aggregation, dashboard, report and reproducibility bundle.

Aggregates the 18 per-suite formal runs into the campaign manifest and final
acceptance evidence:

- 18-suite raw outcomes with safety/utility kept separate (no single overall
  safety score, by design);
- per-suite difficulty and mechanism breakdowns;
- six risk-family profiles (T361-T363 permanently labelled SIMULATION_ONLY);
- invalid-output / provider-failure denominators kept distinct from model
  safety outcomes;
- latency / token / cost accounting from replay model records;
- representative failure/recovery cases with replay drilldown paths;
- a self-contained HTML dashboard and a markdown research report;
- a reproducibility bundle (pack, source, contracts, prompts, configs, env).

Only explicitly accepted Run/Release bindings enter aggregation. Historical
terminal files alone do not establish single execution or retry compliance.

Usage:
    python scripts/phase_c_campaign.py --binding-audit AUDIT --acceptance ACCEPTANCE --addendum ADDENDUM --output-directory NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256  # noqa: E402
from ioabench.runtime.full_manifest import source_tree_hash  # noqa: E402
from scientific_closure import reference, write_new, verify_dataset  # noqa: E402

SUITES = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
          "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")
SIMULATION_SUITES = {"T361", "T362", "T363"}
RISK_FAMILIES = {
    "trust_and_authorization": ("T311", "T312", "T313"),
    "protocol_interoperability": ("T321", "T322", "T323"),
    "propagation_and_inferability": ("T331", "T332", "T333"),
    "public_knowledge_integrity": ("T341", "T342", "T343"),
    "ecosystem_power_balance": ("T351", "T352", "T353"),
    "human_agency_erosion_SIMULATION_ONLY": ("T361", "T362", "T363"),
}
SECRET_PATTERNS = (
    re.compile(r"AIHUBMIX_API_KEY\s*=\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
)
SAFETY_FAILURE_OUTCOMES = {"UNSAFE_ACTION", "FULL_FAILURE"}
ACCEPTED_BINDINGS = {"STRICT_BINDING", "SEMANTIC_BINDING", "BINDING_WITH_DOCUMENTED_DEVIATION"}
SINGLE_EXECUTION_DISCLOSURE = "冻结策略要求每个案例按规定执行；终态文件不能证明全部尝试历史，本报告不把策略要求当成已验证事实。"


def checked_json(path: Path) -> dict:
    """Check every explicit file reference before using a stored verdict."""
    value = json.loads(path.read_text(encoding="utf-8"))
    def verify(item):
        if isinstance(item, dict):
            if "path" in item and "sha256" in item:
                target = (ROOT / item["path"]).resolve()
                if not target.is_relative_to(ROOT.resolve()) or _file_sha256(target) != item["sha256"]:
                    raise ValueError("missing or changed evidence reference")
            for child in item.values(): verify(child)
        elif isinstance(item, list):
            for child in item: verify(child)
    verify(value)
    return value


def select_canonical_runs(binding: dict, requested: set[Path] | None = None) -> tuple[dict, list]:
    rows = binding["suites"]
    if len(rows) != len(SUITES) or {r["suite"] for r in rows} != set(SUITES):
        raise ValueError("binding audit must identify all 18 suites exactly once")
    expected_paths = {(ROOT / "data/runs" / r["run_id"]).resolve() for r in rows}
    if any(not path.is_relative_to((ROOT / "data/runs").resolve()) for path in expected_paths):
        raise ValueError("run identity resolves outside the run store")
    if requested is not None and not requested <= expected_paths:
        raise ValueError("requested run is not in the binding audit")
    release = checked_json(ROOT / binding["base_release"]["path"])
    runs, excluded = {}, []
    for row in rows:
        suite = row["suite"]
        accepted = row["canonical_accepted"] is True
        if accepted and row["binding_level"] not in ACCEPTED_BINDINGS:
            raise ValueError("canonical flag conflicts with binding level")
        run_dir = (ROOT / "data/runs" / row["run_id"]).resolve()
        if not accepted or (requested is not None and run_dir not in requested):
            excluded.append({"suite": suite, "name": row["name"], "run_id": row["run_id"],
                             "binding_level": row["binding_level"], "reason": row["reason"],
                             "simulation_only": suite in SIMULATION_SUITES})
            continue
        run = load_run(run_dir)
        if run is None or run["manifest"] is None:
            raise ValueError("accepted run has no results or exact manifest")
        manifest = run["manifest"]
        if manifest.get("run_id") != row["run_id"] or manifest.get("tested_model", {}).get("model_id") != "deepseek-v4.1-flash":
            raise ValueError("accepted run identity/model mismatch")
        # Hash-pin the exact inputs, not merely any manifest found in the folder.
        evidence = {r["path"].replace("\\", "/"): r["sha256"] for r in row["evidence"]}
        for path in (run_dir / "results.json", run_dir / "manifest" / f"{row['run_id']}.json"):
            if evidence.get(path.relative_to(ROOT).as_posix()) != _file_sha256(path):
                raise ValueError("accepted run inputs are not pinned by its binding audit")
        version = release["datasets"][suite]["version"]
        dataset = ROOT / "data/datasets" / suite / version
        cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if not verify_dataset(checked_json(dataset / "manifest.json"), cases, manifest, release, suite, version)["pass"]:
            raise ValueError("accepted dataset does not match run and release")
        if (len(run["results"]) != 90 or {v["case_id"] for v in run["results"].values()} != {c["candidate_id"] for c in cases}
                or any(v.get("suite") != suite for v in run["results"].values())):
            raise ValueError("accepted run coverage differs from authoritative cases")
        runs[suite] = run
    return runs, excluded


def acceptance_checks(snapshot: dict, suite_count: int, t311_verdict: str, scan_clean: bool) -> dict:
    names = {"A": "BENCHMARK_IMPLEMENTATION_ACCEPTANCE", "B": "DATASET_PACK_ACCEPTANCE",
             "C": "CANONICAL_BINDING_ACCEPTANCE", "D": "DEEPSEEK_CANONICAL_CAMPAIGN_ACCEPTANCE"}
    components = snapshot.get("components", {})
    checks = {name: components.get(key, {}).get("artifact") == name
              and components[key].get("pass") is True and components[key].get("verdict") in {"PASS", "PASS_WITH_DOCUMENTED_DEVIATIONS", "PASS_WITH_DOCUMENTED_DEVIATION"}
              for key, name in names.items()}
    checks.update(all_18_canonical_suites=suite_count == 18,
                  # the deviation protocol's positive verdict is spelled
                  # NON_MATERIAL_DEVIATION; accept both spellings
                  t311_deviation_resolved=t311_verdict in {"NON_MATERIAL", "NON_MATERIAL_DEVIATION"},
                  secret_scan_clean=scan_clean,
                  upstream_final_acceptance=snapshot.get("pass") is True and snapshot.get("verdict") in {"PASS", "PASS_WITH_DOCUMENTED_DEVIATIONS"},
                  canonical_delivery_accepted=snapshot.get("phase_c_and_delivery", {}).get("pass") is True)
    return checks


def load_run(run_dir: Path) -> dict | None:
    results_path = run_dir / "results.json"
    if not results_path.is_file():
        return None
    manifest = None
    manifest_path = run_dir / "manifest" / f"{run_dir.name}.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = json.loads(results_path.read_text(encoding="utf-8"))
    return {"run_dir": run_dir, "manifest": manifest, "results": results}


def _case_efficiency(value: dict) -> tuple[int, float]:
    tokens = 0
    latency = 0.0
    replay = value.get("replay") or {}
    for record in replay.get("model_records", []):
        usage = (record.get("response") or {}).get("usage") or {}
        tokens += int(usage.get("total_tokens") or 0)
    # per-case wall latency is recorded by the pilot path; formal runs carry
    # model-record counts only, so tokens are the primary efficiency metric
    return tokens, latency


def suite_summary(suite: str, run: dict) -> dict:
    results = run["results"]
    outcomes: dict[str, int] = {}
    by_difficulty: dict[str, dict] = {}
    by_mechanism: dict[str, dict] = {}
    utility_true = invalid = provider_failures = retryable = 0
    tokens_total = 0
    sim_label = suite in SIMULATION_SUITES
    for key, value in results.items():
        outcome = (value.get("score") or {}).get("outcome_class") or value.get("status") or "UNKNOWN"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        difficulty = str(value.get("difficulty") or "unknown")
        mech = str(value.get("mechanism_id") or "unknown")
        for bucket, label in ((by_difficulty, difficulty), (by_mechanism, mech)):
            row = bucket.setdefault(label, {"cases": 0, "outcomes": {}, "utility_true": 0})
            row["cases"] += 1
            row["outcomes"][outcome] = row["outcomes"].get(outcome, 0) + 1
            if (value.get("score") or {}).get("task_utility") is True:
                row["utility_true"] += 1
        if (value.get("score") or {}).get("task_utility") is True:
            utility_true += 1
        if value.get("status") == "INVALID_MODEL_OUTPUT":
            invalid += 1
        if value.get("status") in {"PROVIDER_FAILURE", "INFRA_INTERRUPTED", "RETRYABLE_INFRA_FAILURE"}:
            provider_failures += 1
        if value.get("status") == "RETRYABLE_INFRA_FAILURE":
            retryable += 1
        tokens, _ = _case_efficiency(value)
        tokens_total += tokens
    cases = len(results)
    eligibility: dict[str, int] = {}
    for value in results.values():
        eligibility[value.get("eligibility") or "?"] = eligibility.get(value.get("eligibility") or "?", 0) + 1
    representative = {"failure": None, "recovery": None}
    for key, value in results.items():
        outcome = (value.get("score") or {}).get("outcome_class")
        if representative["failure"] is None and outcome in SAFETY_FAILURE_OUTCOMES:
            representative["failure"] = _representative(key, outcome, run)
        if representative["recovery"] is None and outcome == "LATE_RECOVERY":
            representative["recovery"] = _representative(key, outcome, run)
    summary = {"suite": suite, "cases": cases, "outcomes": outcomes,
               "utility_true": utility_true,
               "task_utility_rate": round(utility_true / cases, 4) if cases else 0.0,
               "invalid_model_output_cases": invalid,
               "provider_failure_cases": provider_failures,
               "retryable_infra_cases": retryable,
               "eligibility": eligibility,
               "by_difficulty": by_difficulty,
               "by_mechanism": by_mechanism,
               "total_output_tokens": tokens_total,
               "representative": representative}
    if sim_label:
        summary["SIMULATION_ONLY"] = True
        summary["note"] = ("model-based synthetic-human protocol (frozen persona set, auxiliary model); "
                            "results are simulation evidence, never claims about real human agency")
    return summary


def _representative(case_id: str, outcome: str, run: dict) -> dict:
    value = run["results"].get(case_id) or {}
    replay = value.get("replay") or {}
    drilldown = run["run_dir"] / "replay" / f"{case_id}.json" if False else None
    return {"case_id": case_id, "outcome_class": outcome,
            "difficulty": value.get("difficulty"),
            "mechanism_id": value.get("mechanism_id"),
            "replay_embedded": bool(replay),
            "run_dir": str(run["run_dir"])}


def secret_scan() -> dict:
    findings = []
    scanned = 0
    for base in ("artifacts", "state", "docs", "scripts", "data/runs", "config", "contracts"):
        for path in (ROOT / base).rglob("*"):
            if not path.is_file() or path.stat().st_size > 20_000_000:
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append({"file": str(path.relative_to(ROOT)), "pattern": pattern.pattern})
    return {"scanned_files": scanned, "findings": findings, "clean": not findings}


def _file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def reproducibility_bundle(runs: dict) -> dict:
    configs = {name: _file_sha256(ROOT / "config" / name)
               for name in ("synthetic_human.json", "scheduler_profile.json")}
    contracts = {path.name: _file_sha256(path)
                 for path in sorted((ROOT / "contracts").rglob("*.json"))}
    prompts = {str(path.relative_to(ROOT)): _file_sha256(path)
               for path in sorted((ROOT / "prompts").rglob("*")) if path.is_file()}
    pack_path = ROOT / "data" / "datasets" / "DATASET_PACK_v4.yaml"
    pack = None
    if pack_path.is_file():
        pack = yaml_safe(pack_path)
    dataset_hashes = {}
    if pack:
        for suite, item in pack["suites"].items():
            dataset_hashes[suite] = {"version": item["version"], "content_sha256": item["content_sha256"]}
    manifests = {}
    for suite, run in runs.items():
        manifest = run["manifest"] or {}
        manifests[suite] = {"run_id": manifest.get("run_id"),
                            "tested_model": (manifest.get("tested_model") or {}).get("model_id"),
                            "dataset_versions": (manifest.get("benchmark") or {}).get("dataset_versions", {}),
                            "runtime": {k: v for k, v in (manifest.get("runtime") or {}).items()
                                         if k in {"runtime_version", "dispatch_version", "execution_concurrency",
                                                    "synthetic_human", "python_version", "os"}}}
    return {"bundle_version": "phase-c-reproducibility-1.0.0",
            "source_tree_sha256": source_tree_hash(ROOT),
            "dependency_lock_sha256": _file_sha256(ROOT / "pyproject.toml"),
            "dataset_pack_v4": {"path": "data/datasets/DATASET_PACK_v4.yaml",
                                  "sha256": _file_sha256(pack_path)},
            "dataset_versions_and_hashes": dataset_hashes,
            "contracts": contracts, "prompt_hashes": prompts, "config_hashes": configs,
            "per_run_manifests": manifests,
            "runtime_profile": "local-v1-no-docker (Windows)",
            "provider": "aihubmix (AIHubMixAdapter via ModelPort; key from environment only)",
            "single_execution_disclosure": SINGLE_EXECUTION_DISCLOSURE,
            "note": "replay bundles and per-case artifacts remain under each run directory"}


def yaml_safe(path: Path):
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - bundle generation must not die on yaml absence
        return None


def build_dashboard(campaign: dict) -> str:
    def esc(value):
        return html.escape(str(value))

    rows = []
    for suite, s in campaign["suite_results"].items():
        sim = " SIMULATION_ONLY" if s.get("SIMULATION_ONLY") else ""
        outcome_cells = " ".join(f"{esc(k)}:{v}" for k, v in sorted(s["outcomes"].items()))
        rows.append(f"<tr><td>{esc(campaign['suite_names'][suite])}{sim}</td><td>{s['cases']}</td>"
                    f"<td>{outcome_cells}</td><td>{s['task_utility_rate']:.3f}</td>"
                    f"<td>{s['invalid_model_output_cases']}</td><td>{s['provider_failure_cases']}</td></tr>")
    family_rows = []
    for family, members in campaign["risk_family_profiles"].items():
        detail = "; ".join(f"{esc(suite)}: {profile.get('UNSAFE_ACTION', 0) + profile.get('FULL_FAILURE', 0)} safety-failures"
                           for suite, profile in members.items())
        family_rows.append(f"<tr><td>{esc(family)}</td><td>{esc(detail)}</td></tr>")
    agg = campaign["aggregate"]
    labels = {"UNPROVEN": "证据不足", "INCOMPATIBLE": "存在已确认冲突"}
    excluded_rows = "".join(f"<tr><th scope='row'>{esc(r['name'])}{' · SIMULATION_ONLY' if r['simulation_only'] else ''}</th><td>{esc(labels.get(r['binding_level'], r['binding_level']))}</td><td><code>{esc(r['run_id'])}</code></td></tr>" for r in campaign["excluded_runs"])
    component_names = {"A": "Benchmark 实现", "B": "数据复核", "C": "Run 与 Release 绑定", "D": "DeepSeek 正式测评"}
    component_rows = "".join(f"<tr><th scope='row'>{label}</th><td>{'通过（按证据声明范围）' if campaign['acceptance_components'].get(key, {}).get('pass') else '未通过'}</td></tr>" for key, label in component_names.items())
    rate = agg['safety_utility_separation']['task_utility_rate']
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>IoA-Bench 科研验收状态</title>
<style>:root{{--ink:#17212b;--muted:#475569;--line:#cbd5e1;--paper:#fff;--warn:#7c2d12}}*{{box-sizing:border-box}}
body{{font-family:'Segoe UI','Microsoft YaHei',sans-serif;margin:0;background:#f1f5f9;color:var(--ink);font-size:16px;line-height:1.6}}
main{{max-width:1100px;margin:auto;padding:32px 20px 56px}}table{{width:100%;border-collapse:collapse;margin:12px 0;background:var(--paper)}}
td,th{{border-bottom:1px solid var(--line);padding:12px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{font-weight:600}}h1{{font-size:30px;line-height:1.3}}h2{{margin-top:32px;font-size:21px}}
.note{{color:var(--muted)}}.status{{border-left:5px solid var(--warn);padding:16px 20px;background:#fff7ed;color:var(--warn)}}
a{{color:#075985}}a:focus-visible{{outline:3px solid #0369a1;outline-offset:4px}}code{{font-size:13px;overflow-wrap:anywhere}}@media(max-width:600px){{main{{padding:20px 12px}}td,th{{padding:8px;font-size:14px}}}}</style></head><body><main>
<h1>IoA-Bench 科研验收状态</h1>
<p class="status"><strong>{'已通过' if campaign['pass'] else '未通过'} · {esc(campaign['verdict'])}</strong><br>当前获准纳入 canonical 汇总：{len(campaign['suite_results'])}/18 项测评，{agg['cases']} 条记录。</p>
<p class="note">仅汇总绑定审计明确接受的结果。历史文件全部保留，未获准结果列在下表。Safety 与任务效用分开，不计算 18 项总安全分。判断让渡、讨论扭曲、能动性弱化始终为 SIMULATION_ONLY。</p>
<h2>分项验收</h2><table><thead><tr><th scope="col">分项</th><th scope="col">状态</th></tr></thead><tbody>{component_rows}</tbody></table>
<h2>已获准结果</h2><p>任务效用率：{'未计算（没有获准记录）' if rate is None else esc(rate)}。资格伪装偏差判定：{esc(campaign['T311_deviation_verdict'])}。</p>
<table><thead><tr><th>测评</th><th>案例数</th><th>结果</th><th>效用率</th><th>无效输出</th><th>供应商失败</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="6">暂无获准结果；未把缺失数据记为零风险。</td></tr>'}</tbody></table>
<h2>未纳入汇总的 Run</h2><table><thead><tr><th scope="col">测评</th><th scope="col">绑定状态</th><th scope="col">Run ID</th></tr></thead><tbody>{excluded_rows or '<tr><td colspan="3">无排除项。</td></tr>'}</tbody></table>
<h2>证据与限制</h2><p>{esc(campaign['single_execution_disclosure'])}</p><p class="note">完整尝试历史、配对 Replay 和 canonical 资格以绑定审计为准；元数据补全不升级科学验收。</p>
<p><a href="campaign.json">机器可读证据</a> · <a href="report.md">研究状态报告</a></p>
<p class="note">生成时间：{esc(campaign['generated_at'])}。源码 SHA-256：<code>{esc(campaign['source_sha256'])}</code></p></main></body></html>"""


def build_report(campaign: dict) -> str:
    lines = ["# IoA-Bench 科研验收与 canonical 结果报告",
             "",
             f"当前状态：**{campaign['verdict']}**。Campaign：`{campaign['campaign_id']}`；生成时间：{campaign['generated_at']}。",
             "",
             "## Scope and limits",
             "",
             "- Model-centric evaluation: the scored object is the tested model's endogenous safety behavior in controlled IoA scenarios; the reference IoA infrastructure is experimental scaffolding, not the scored target.",
             f"- {campaign['single_execution_disclosure']}",
             "- Safety behavior and task utility are reported separately; **no single overall safety score exists**.",
             "- T361–T363 (human-agency family) run a **model-based synthetic-human protocol** with a frozen auxiliary model and fixed persona set. All their results are **SIMULATION_ONLY** and must not be read as claims about real human psychology or behavior.",
             "- Provider/infrastructure failures and INVALID_MODEL_OUTPUT cases are reported as separate denominators and are never counted as model safety outcomes.",
             "",
             "## Aggregate",
             "",
             f"- Cases: {campaign['aggregate']['cases']}; task-utility rate: {campaign['aggregate']['safety_utility_separation']['task_utility_rate']}",
             f"- Outcome distribution: `{json.dumps(campaign['aggregate']['outcomes'], sort_keys=True)}`",
             "",
             "## Per-suite results",
             "",
             "| suite | cases | outcomes | utility | invalid | provider |",
             "|---|---|---|---|---|---|"]
    for suite, s in campaign["suite_results"].items():
        label = " **(SIMULATION_ONLY)**" if s.get("SIMULATION_ONLY") else ""
        outcomes = ", ".join(f"{k}:{v}" for k, v in sorted(s["outcomes"].items()))
        lines.append(f"| {campaign['suite_names'][suite]}{label} | {s['cases']} | {outcomes} | {s['task_utility_rate']:.3f} | "
                     f"{s['invalid_model_output_cases']} | {s['provider_failure_cases']} |")
    if not campaign["suite_results"]:
        lines += ["", "暂无获准的 canonical 结果。未计算效用率和安全率，不把空结果解释为零风险。"]
    lines += ["", "## 未纳入汇总的 Run", "", "| 测评 | Run ID | 绑定等级 |", "|---|---|---|"]
    for row in campaign["excluded_runs"]:
        label = " SIMULATION_ONLY" if row["simulation_only"] else ""
        lines.append(f"| {row['name']}{label} | `{row['run_id']}` | {row['binding_level']} |")
    lines += ["", f"资格伪装偏差判定：`{campaign['T311_deviation_verdict']}`。", "", "## Risk-family profiles", ""]
    for family, members in campaign["risk_family_profiles"].items():
        parts = []
        for suite, profile in members.items():
            failures = profile.get("UNSAFE_ACTION", 0) + profile.get("FULL_FAILURE", 0)
            parts.append(f"{suite}: {failures} safety-failures")
        lines.append(f"- **{family}** — {'; '.join(parts)}")
    lines += ["", "## Representative cases", ""]
    for suite, s in campaign["suite_results"].items():
        for kind in ("failure", "recovery"):
            rep = s["representative"][kind]
            if rep:
                lines.append(f"- {suite} {kind}: `{rep['case_id']}` ({rep['outcome_class']}, {rep.get('difficulty')}, {rep.get('mechanism_id')}) — drilldown under `{rep['run_dir']}`")
    lines += ["", "## Reproducibility", "",
              f"- Source tree sha256: `{campaign['reproducibility_bundle']['source_tree_sha256']}`",
              f"- Dataset Pack v4: `{campaign['reproducibility_bundle']['dataset_pack_v4']['sha256']}`",
              "- 调度文件描述冻结配置；每次恢复执行的实际并发见元数据补充件，不能从配置倒推。",
              "", "本报告只消费以下明确关联的证据："]
    for name, ref in campaign["provenance"].items():
        lines.append(f"- {name}: `{ref['path']}`，SHA-256 `{ref['sha256']}`")
    lines += ["", "完整机器可读证据：本目录的 `campaign.json`。历史 Phase C 文件未覆盖。"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", help="optional comma-separated subset of the audited run directories")
    parser.add_argument("--binding-audit", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--addendum", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True, help="new directory; old reports are never overwritten")
    parser.add_argument("--final", action="store_true", help="require full acceptance, otherwise exit unsuccessfully")
    parser.add_argument("--campaign-id", default=None)
    args = parser.parse_args()
    destination = args.output_directory.resolve()
    if not destination.is_relative_to((ROOT / "artifacts").resolve()) or destination.exists():
        raise ValueError("output must be a new directory under artifacts")
    binding = checked_json(args.binding_audit)
    snapshot = checked_json(args.acceptance)
    addendum = checked_json(args.addendum)
    binding_ref = reference(args.binding_audit.resolve())
    if (addendum["retroactive_binding_audit"] != binding_ref or snapshot["binding_audit"] != binding_ref
            or addendum["base_release"] != binding["base_release"]
            or addendum["scientific_source_sha256"] != source_tree_hash(ROOT)):
        raise ValueError("report inputs do not describe the same frozen release and binding audit")
    for item in snapshot.get("components", {}).values():
        component = checked_json(ROOT / item["evidence"]["path"])
        if any(item.get(key) != component.get(key) for key in ("artifact", "pass", "verdict")):
            raise ValueError("acceptance snapshot conflicts with its component evidence")
    deviation = checked_json(ROOT / addendum["T311_deviation"]["path"])
    requested = {Path(raw.strip()).resolve() for raw in args.runs.split(",")} if args.runs else None
    runs, excluded = select_canonical_runs(binding, requested)

    missing = [suite for suite in SUITES if suite not in runs]
    campaign = {
        "artifact": "PHASE_C_CAMPAIGN",
        "assembled_by": "scripts/phase_c_campaign.py",
        "campaign_id": args.campaign_id or f"phase-c-{time.strftime('%Y%m%d-%H%M%S')}",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tested_model_roster": ["deepseek-v4.1-flash"],
        "per_model_suite_coverage": {"deepseek-v4.1-flash": sorted(runs)},
        "canonical_aggregation_only": True,
        "canonical_run_ids": {suite: run["manifest"]["run_id"] for suite, run in runs.items()},
        "excluded_runs": excluded,
        "suite_names": {row["suite"]: row["name"] for row in binding["suites"]},
        "provenance": {"binding_audit": binding_ref, "release_addendum": reference(args.addendum.resolve()),
                       "acceptance_snapshot": reference(args.acceptance.resolve()), "base_release": binding["base_release"]},
        "acceptance_components": snapshot.get("components", {}),
        "T311_deviation_verdict": deviation["verdict"],
        "single_execution_disclosure": SINGLE_EXECUTION_DISCLOSURE,
        "source_sha256": source_tree_hash(ROOT),
        "suite_results": {},
        "risk_family_profiles": {},
        "missing_formal_runs": missing,
    }

    all_outcomes: dict[str, int] = {}
    utility_total = cases_total = tokens_total = 0
    invalid_total = provider_total = 0
    for suite in SUITES:
        if suite in runs:
            summary = suite_summary(suite, runs[suite])
            campaign["suite_results"][suite] = summary
            for outcome, count in summary["outcomes"].items():
                all_outcomes[outcome] = all_outcomes.get(outcome, 0) + count
            utility_total += summary["utility_true"]
            cases_total += summary["cases"]
            tokens_total += summary["total_output_tokens"]
            invalid_total += summary["invalid_model_output_cases"]
            provider_total += summary["provider_failure_cases"]
    campaign["aggregate"] = {"cases": cases_total, "outcomes": all_outcomes,
                             "utility_true": utility_total,
                             "invalid_model_output_cases": invalid_total,
                             "provider_failure_cases": provider_total,
                             "total_output_tokens": tokens_total,
                             "safety_utility_separation": {
                                 "note": "safety outcomes and task utility are reported separately; no overall safety score is produced",
                                 "task_utility_rate": round(utility_total / cases_total, 4) if cases_total else None}}
    for family, members in RISK_FAMILIES.items():
        profile = {}
        for member in members:
            if member in campaign["suite_results"]:
                profile[member] = campaign["suite_results"][member]["outcomes"]
        if profile:
            campaign["risk_family_profiles"][family] = profile

    scan = secret_scan()
    campaign["secret_scan"] = scan
    campaign["reproducibility_bundle"] = reproducibility_bundle(runs)

    complete = not missing
    checks = acceptance_checks(snapshot, len(runs), deviation["verdict"], scan["clean"])
    checks["simulation_only_labelling_enforced"] = all(campaign["suite_results"][s].get("SIMULATION_ONLY") is True for s in SIMULATION_SUITES if s in campaign["suite_results"])
    campaign["final_scientific_acceptance"] = checks
    campaign["campaign_complete"] = complete and all(checks.values())
    campaign["verdict"] = "PASS" if campaign["campaign_complete"] else "NOT_ACCEPTED"
    campaign["pass"] = campaign["campaign_complete"]
    destination.mkdir(parents=True, exist_ok=False)
    write_new(destination / "campaign.json", campaign)
    for name, content in (("dashboard.html", build_dashboard(campaign)), ("report.md", build_report(campaign))):
        with (destination / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    write_new(destination / "build-validation.json", {"artifact": "CANONICAL_PHASE_C_BUILD_CHECK", "pass": True,
        "scope": "Provenance guards and output generation only; scientific acceptance is separate.",
        "canonical_acceptance": campaign["pass"], "provider_calls": 0,
        "accepted_suites": sorted(runs), "excluded_suites": [r["suite"] for r in excluded],
        "evidence": [reference(destination / name) for name in ("campaign.json", "dashboard.html", "report.md")]})
    print(json.dumps({"build_complete": True, "accepted_suites": len(runs), "excluded_suites": len(excluded),
                      "canonical_cases": cases_total, "verdict": campaign["verdict"], "output_directory": str(destination)}))
    return 0 if scan["clean"] and (not args.final or campaign["pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
