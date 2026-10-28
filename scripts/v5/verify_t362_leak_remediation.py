"""Append-only, provider-free verification of the classic T362 public projection revision."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5 import evaluation, replay
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.core.policy import attachment_of
from ioabench.v5.gates import check_pair
from ioabench.v5.suites import t362


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def historical_files(root: Path) -> list[Path]:
    paths = set((root / "data/v5/datasets/T362").glob("*/cases.jsonl"))
    for folder in ("artifacts/v5/evaluations", "artifacts/v5/pilot", "artifacts/v5/manual_18"):
        paths.update((root / folder).rglob("cases.jsonl"))
        paths.update((root / folder).rglob("results.jsonl"))
    for folder in (root / "data/runs").glob("T362*"):
        paths.update(folder.glob("pilot-replay/*.json"))
    return sorted(paths)


def documents(path: Path):
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8-sig") as stream:
            for index, line in enumerate(stream, 1):
                if line.strip():
                    yield index, json.loads(line)
    else:
        yield 1, json.loads(path.read_text(encoding="utf-8-sig"))


def scan_history(root: Path, paths: list[Path]) -> dict:
    cases, exposures, errors = [], [], []
    for path in paths:
        try:
            for line, doc in documents(path):
                if not isinstance(doc, dict):
                    continue
                if not str(doc.get("suite_id", doc.get("case_id", ""))).startswith("T362"):
                    continue
                if doc.get("suite_id") == "T362" and isinstance(doc.get("world"), dict):
                    world, provenance = doc["world"], doc.get("provenance", {})
                    profile = provenance.get("required_scenario_profile")
                    has_field = "evidence_post_id" in world
                    cases.append({"path": str(path.relative_to(root)), "line": line,
                        "case_id": doc.get("case_id"), "generator_version": provenance.get("generator_version"),
                        "required_scenario_profile": profile, "world_has_preselected_id": has_field,
                        "projection_disposition": "LEGACY_CLASSIC_EXPOSURE_REPRODUCIBLE" if has_field and not profile
                            else "AUTHORED_PROFILE_OMITS_EXPLICIT_ID" if profile else "NO_EXPLICIT_ID_IN_WORLD",
                        "case_sha256": canonical_sha256(doc)})
                stack = [doc]
                while stack:
                    item = stack.pop()
                    if isinstance(item, dict):
                        messages = item.get("messages")
                        if isinstance(messages, list):
                            hits = [i for i, message in enumerate(messages) if isinstance(message, dict)
                                and message.get("role") in {"user", "tool"}
                                and '"evidence_post_id"' in str(message.get("content", ""))]
                            if hits:
                                exposures.append({"path": str(path.relative_to(root)), "line": line,
                                    "case_id": doc.get("case_id"), "model_id": doc.get("model_id"),
                                    "versions": doc.get("versions"), "message_indices": hits})
                        stack.extend(value for key, value in item.items() if key != "messages" and isinstance(value, (dict, list)))
                    elif isinstance(item, list):
                        stack.extend(value for value in item if isinstance(value, (dict, list)))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append({"path": str(path.relative_to(root)), "error": f"{type(exc).__name__}: {exc}"})
    return {"scope": ["data/v5/datasets/T362/*/cases.jsonl", "artifacts/v5/{evaluations,pilot,manual_18}/**/{cases,results}.jsonl",
                      "data/runs/T362*/pilot-replay/*.json"],
        "files_scanned": len(paths), "classic_case_occurrences": len(cases),
        "legacy_stock_exposure_case_occurrences": sum(row["projection_disposition"] == "LEGACY_CLASSIC_EXPOSURE_REPRODUCIBLE" for row in cases),
        "actual_request_exposure_occurrences": len(exposures), "cases": cases, "actual_request_exposures": exposures,
        "actual_exposed_case_ids": sorted({row["case_id"] for row in exposures if row["case_id"]}),
        "actual_exposed_files": sorted({row["path"] for row in exposures}),
        "read_errors": errors, "deduplication": "Occurrences are not independent cases or runs; no scientific denominator is inferred.",
        "limitation": "Named canonical local stores only; compressed snapshots, archives, arbitrary logs and semantic prose are not exhaustively scanned."}


def verify(root: Path, out: Path) -> dict:
    if out.exists() and any(out.iterdir()):
        raise ValueError("output directory must be new or empty; historical evidence is immutable")
    out.mkdir(parents=True, exist_ok=True)
    source_before = source_tree_hash(ROOT)
    paths = historical_files(root)
    before = {str(path.relative_to(root)): sha(path) for path in paths}
    history = scan_history(root, paths)
    write(out / "HISTORICAL_IMPACT.json", history)
    pairs = t362.generate(20261019, families=5)
    cases = [case for pair in pairs for case in pair]
    inputs = out / "NEW_CASES.jsonl"
    inputs.write_text("".join(json.dumps(case.as_dict(), ensure_ascii=False, sort_keys=True) + "\n" for case in cases), encoding="utf-8")
    gates = [check_pair(*pair) for pair in pairs]
    write(out / "REFERENCE_GATES.json", gates)
    old = cases[0].as_dict()
    old["world"]["evidence_post_id"] = old["oracle"]["evidence_post_id"]
    old["provenance"] = {"generator_version": "t362-generator-5.1.0"}
    old_digest = canonical_sha256(old)
    loaded = case_from_dict(old)
    legacy = attachment_of(t362.T362LegacyScenario()._forum_message(loaded.world))
    marker = "PRIVATE_PRESELECTED_ANSWER_DO_NOT_RENDER"
    poisoned = json.loads(json.dumps(old["world"]))
    poisoned["evidence_post_id"] = marker
    poisoned["recommended_digest"] = [marker]
    poisoned["curator_hint"] = f"Accepted answer: {marker}"
    poisoned["posts"][0]["preferred_post"] = marker
    poisoned["evidence_records"][0]["preferred_post"] = marker
    poisoned["evidence_records"][0]["measurement"]["expected_answer"] = marker
    current = attachment_of(t362.T362Scenario()._forum_message(poisoned))
    leakage_checks = {"legacy_explicit_leak_reproduced": legacy.get("evidence_post_id") == old["oracle"]["evidence_post_id"],
        "explicit_field_and_metadata_aliases_removed": marker not in json.dumps(current) and "evidence_post_id" not in current,
        "primary_records_preserved": current["evidence_records"][0]["measurement"] == old["world"]["evidence_records"][0]["measurement"],
        "legacy_case_load_preserves_content": canonical_sha256(loaded.as_dict()) == old_digest == canonical_sha256(old),
        "new_cases_oracle_separation": all("evidence_post_id" not in case.world and "evidence_post_id" in case.oracle for case in cases)}
    write(out / "LEAKAGE_REPRODUCTION.json", {"legacy_projection": legacy, "new_projection": current, "checks": leakage_checks})
    profile = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
    runtime = out / "runtime"
    summary = evaluation.run_batch(runtime, inputs, run_id="t362-leak-remediation", profile=profile,
        reference_policy="witness", parameters={})
    run_dir = runtime / "artifacts/v5/evaluations/t362-leak-remediation"
    # A successful resume publishes a new report and updates its checkpoint reference by design.
    retained = [*(run_dir / name for name in ("cases.jsonl", "manifest.json", "results.jsonl")),
                *(runtime / "data/runs/t362-leak-remediation").rglob("*.jsonl")]
    run_before = {str(path.relative_to(runtime)): sha(path) for path in retained}
    replay_checks = [replay.replay_case(runtime, "t362-leak-remediation", case.case_id) for case in cases]
    execute = evaluation.execute_case
    def forbidden_execute(*args, **kwargs):
        raise AssertionError("resume attempted to execute a terminal case")
    evaluation.execute_case = forbidden_execute
    try:
        resumed = evaluation.run_batch(runtime, inputs, run_id="t362-leak-remediation", profile=profile,
            reference_policy="witness", parameters={}, resume=True)
    finally:
        evaluation.execute_case = execute
    rows = evaluation.read_results(run_dir)
    observation_checks = []
    for row in rows:
        messages = [message for record in row["trace"]["records"] for message in record["request"]["messages"]]
        observation_checks.append({"case_id": row["case_id"], "model_calls": row["model_calls"],
            "no_preselection_in_any_model_request": all("evidence_post_id" not in str(message.get("content", "")) for message in messages),
            "safety": row["score"]["safety"], "utility": row["score"]["utility"], "simulation_only": row["simulation_only"]})
    source_after = source_tree_hash(ROOT)
    checks = {**leakage_checks, "all_reference_gates": all(row["passed"] for row in gates),
        "strict_replay": all(row["passed"] and row["provider_calls"] == 0 for row in replay_checks),
        "resume_no_execution": summary == resumed,
        "run_inputs_results_journals_unchanged_by_resume": all(sha(runtime / path) == value for path, value in run_before.items()),
        "old_history_unchanged": all(sha(root / path) == value for path, value in before.items()),
        "no_preselection_in_multiturn_requests": all(row["no_preselection_in_any_model_request"] for row in observation_checks),
        "simulation_only": all(row["simulation_only"] for row in observation_checks),
        "source_stable_during_run": source_before == source_after}
    report = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "scenario_version": t362.SCENARIO_VERSION, "generator_version": t362.GENERATOR_VERSION,
        "scorer_version": t362.SCORER_VERSION, "source_before": source_before, "source_after": source_after,
        "new_pairs": len(pairs), "new_cases": len(cases), "reference_executions": sum(len(row["runs"]) for row in gates),
        "runner_cases": len(rows), "strict_replays": len(replay_checks), "provider_calls": 0,
        "history": {key: value for key, value in history.items() if key not in {"cases", "actual_request_exposures"}},
        "observations": observation_checks, "replay_checks": replay_checks,
        "scientific_validity": "NOT_ESTABLISHED", "historical_scientific_disposition": "PI_DECISION_REQUIRED",
        "independent_content_review": "NOT_RUN", "new_online_execution": "NOT_RUN", "formal_freeze": "NOT_RUN",
        "limitations": ["Public natural-language bodies remain authentic task evidence; arbitrary semantic answer leakage requires independent review.",
            "Known metadata selectors are excluded; arbitrary covert encoding is not certified absent.",
            "Legacy 5.1.0 scenario is retained only for explicit reproduction; historical strict replay still requires its pinned source.",
            "Historical evidence is scanned and preserved, not automatically excluded, rescored or scientifically accepted."]}
    write(out / "T362_LEAK_REMEDIATION.json", report)
    write(out / "HISTORICAL_FILE_HASHES.json", before)
    text = f"""# 讨论扭曲测评（T362）经典公开投影修复

工程判定：**{report['status']}**。新 scenario `{t362.SCENARIO_VERSION}` / generator `{t362.GENERATOR_VERSION}`；评分 `{t362.SCORER_VERSION}` 原样保留。全程 `SIMULATION_ONLY`，新增 Provider 调用 0。

旧5.1.0公开消息将 `world.evidence_post_id` 直接交给SUT，已用显式旧scenario复现。新生成不再将该字段放入world，公开投影采用受限事实字段，拒绝传播等价预选metadata；真实帖文、证据引用及测量记录保留。参考策略只从公开证据引用/报告推导，不读取Oracle。旧case可原样加载；精确历史Replay仍须恢复原source快照。

实际执行 {len(pairs)} 对/{len(cases)} 例、{report['reference_executions']} 次正负/恢复参考执行、{len(rows)} 条runner轨迹、{len(replay_checks)} 次严格Replay及零执行resume。各项原始结果见同目录JSON与runtime。`checks` 全部为真才判PASS；测试脚本存在不构成验收。

历史扫描范围限定为 `HISTORICAL_IMPACT.json` 列明的canonical stores：{history['files_scanned']} 个文件，{history['classic_case_occurrences']} 条经典case出现，{history['legacy_stock_exposure_case_occurrences']} 条旧stock投影可复现暴露，{history['actual_request_exposure_occurrences']} 处保留请求出现显式字段。出现次数不是独立样本数；压缩历史、任意日志及语义正文未穷尽。所枚举旧文件SHA保护结果：{checks['old_history_unchanged']}。

PI裁决所需：旧stock暴露行是否从科研分析剔除、哪些样本需在新冻结协议下重测；旧generic-summary证据是否足以支持原规范操作化；新生成测量记录及真实帖文是否满足构念有效性。工程修复不能自行批准上述科学处置。旧profile已去掉显式ID，不自动等同无语义泄漏。

独立内容审核、新在线执行、正式冻结：NOT_RUN。科学有效性：NOT_ESTABLISHED。历史科学处置：PI_DECISION_REQUIRED。没有修改冻结数据、原评分、正式SUT、旧运行或Gate门槛。
"""
    (out / "T362_LEAK_REMEDIATION.md").write_text(text, encoding="utf-8")
    write(out / "SHA256SUMS.json", {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.json"})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace.resolve(), args.out.resolve())
    print(json.dumps({key: result[key] for key in ("status", "checks", "new_cases", "reference_executions", "strict_replays", "provider_calls")}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
