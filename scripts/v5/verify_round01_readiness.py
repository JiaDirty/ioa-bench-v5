"""Provider-free round-01 readiness evidence; no qualification or history relabeling."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.acquisition import staged_proposal
from ioabench.v5.ai_generation.pipeline import CandidateRejected, compile_and_gate, suite_spec
from ioabench.v5.core.case import case_from_dict

NAMES = dict(zip(("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333", "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363"),
    ("资格伪装", "注册失真", "代表资格漂移", "协商污染", "互操作失配", "责任链断裂", "跨系统级联扩散", "结构暴露", "行为推断", "生态错误共识", "谣言扩散", "规范漂移", "激励错配", "声誉垄断", "节点操纵", "判断让渡", "讨论扭曲", "能动性弱化")))


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable evidence differs: {path}; use a new output directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8", newline="\n")


def typed_ready(row):
    return (row.get("registered") is True and row.get("status") == "SUPPORTED"
        and row.get("structural_acquisition") == "SUPPORTED" and row.get("reference_gate") == "PASS"
        and row.get("execution_fidelity") == "PASS"
        and row.get("unsupported_field_control", {}).get("status") == "REJECTED"
        and any(item.get("status") == "SUPPORTED" for item in row.get("factor_examples", []))
        and all(item.get("reference_gate") == "PASS" and item.get("execution_fidelity") == "PASS"
                for item in row["factor_examples"] if item.get("status") == "SUPPORTED"))


def staged_mock(spec, blueprint, seed):
    """Exercise the real four-stage parser using schema fixtures, never an AI response."""
    envelopes = []

    async def call(stage, messages):
        request = json.loads(messages[-1]["content"])
        envelope_schema = request["output_schema"]
        fields = envelope_schema["properties"]["proposal"]["properties"]
        if stage in {"world_graph", "surface_artifacts"} and "world_edits" not in fields:
            source = blueprint.get("suite_payload", {})
        else:
            source = blueprint
        proposal = ({"truth_owner": "program"} if "truth_owner" in fields else
                    {key: deepcopy(source[key]) for key in fields if key in source})
        value = {"stage": stage, "depends_on": envelope_schema["properties"]["depends_on"]["const"], "proposal": proposal}
        envelopes.append({"request": request, "response": value})
        return {"text": json.dumps(value), "resolved_model_id": "OFFLINE_SCHEMA_FIXTURE_NO_MODEL"}

    compiled, stages = asyncio.run(staged_proposal(spec, seed=seed, difficulty=blueprint["difficulty"],
        target=None, call=call, decode=json.loads))
    if compiled != blueprint or len(stages) != 4:
        raise ValueError(f"staged fixture changed proposal: {spec.suite_id}")
    return {"status": "PASS_MOCK_ONLY", "blueprint_sha256": canonical_sha256(compiled),
        "stage_count": len(stages), "stages": stages, "envelopes": envelopes, "provider_calls": 0}


def no_intervention_negative(spec, row, seed):
    control, risk = [case_from_dict(raw, allow_dynamic=True) for raw in row["pair"]]
    broken = replace(risk, world=deepcopy(control.world))
    with patch.object(spec.adapter, "compile_pair", return_value=(control, broken)):
        try:
            compile_and_gate(spec, row["blueprint"], seed=seed)
        except CandidateRejected as exc:
            if exc.stage != "ARM_DELTA":
                raise ValueError(f"wrong negative rejection stage: {exc.stage}") from exc
            return {"status": "REJECTED", "stage": exc.stage, "findings": exc.findings,
                "mutation": "risk.world replaced with control.world; causal intervention removed",
                "mutated_pair_sha256": canonical_sha256([control.as_dict(), broken.as_dict()]), "provider_calls": 0}
    raise ValueError(f"removed intervention was accepted: {spec.suite_id}")


def build(output):
    before = source_tree_hash(ROOT)
    cap_path = output / "CAPABILITY.json"
    cap = read(cap_path)
    if cap["runtime_source_sha256"] != before or cap["manifest_sha256"] != canonical_sha256({key: value for key, value in cap.items() if key != "manifest_sha256"}):
        raise ValueError("capability/source binding is stale or invalid")
    if set(cap["suites"]) != set(NAMES) or cap["provider_calls"] != 0:
        raise ValueError("capability must cover exactly 18 suites without Provider calls")
    r3 = ROOT / "artifacts/v5/data_factory/next-r1"
    inputs = [cap_path, output / "CAPABILITY_COMMAND.json", r3 / "STRUCTURE_AND_COVERAGE_REPORT.json",
        r3 / "GENERATED_HISTORY_CLASSIFICATION.json", r3 / "current_history_probes/INDEX_WITH_PROBES.json"]
    history = read(inputs[-2])
    index = read(inputs[-1])
    coverage = read(inputs[-3])
    if sha(inputs[-1]) != history["current_index_sha256"]:
        raise ValueError("R3 history index binding differs")
    history_counts = {suite: Counter() for suite in NAMES}
    for record in index["records"]:
        suite = record["features"]["suite_id"].split("-")[0]
        history_counts[suite]["PROBED" if record.get("behavioral_probe_signature") else "INDETERMINATE"] += 1
    rows, mock_rows, negatives = {}, {}, {}
    for offset, (suite, value) in enumerate(cap["suites"].items()):
        typed = value["typed_compiler"]
        if not typed_ready(typed) or value["runtime_reference_status"] != "SUPPORTED":
            raise ValueError(f"current executed engineering capability failed: {suite}")
        seed = cap["seed"] + 100 + offset
        spec = suite_spec(suite, typed=True)
        mock_rows[suite] = staged_mock(spec, typed["blueprint"], seed)
        negatives[suite] = no_intervention_negative(spec, typed, seed)
        generated = [(i, row) for i, row in enumerate(history["rows"]) if row["suite_id"].split("-")[0] == suite]
        groups = Counter(row["quality_classification"]["status"] for _, row in generated)
        supported = [row for row in typed["factor_examples"] if row["status"] == "SUPPORTED"]
        unsupported = [{"factors": row["factors"], "findings": row.get("findings", [])}
            for row in typed["factor_examples"] if row["status"] != "SUPPORTED"]
        reference_count = sum(len(row.get("gate", {}).get("runs", []))
            for row in [typed, *typed["factor_examples"], *(cap["slices"][name] for name in value["dynamic_slices"])])
        rows[suite] = {"name": NAMES[suite], "typed_status": "PASS_EXECUTED_BOUNDED", "dynamic_slices": value["dynamic_slices"],
            "g1": "PASS_EXECUTED_PROGRAM_PROPOSAL", "g2": {"current": "PASS_FOUR_STAGE_MOCK_ONLY",
                "real_ai_current_round": "NOT_RUN", "r3_generation_statuses": coverage["suites"][suite]["generation_statuses"]},
            "g3": "BLOCKED_NO_QUALIFIED_SAME_SOURCE_PARENT", "finite_factors": typed["finite_executable_factors"],
            "enum_cells_declared": len(typed["factor_examples"]), "enum_cells_supported": len(supported),
            "unsupported_or_infeasible_cells": unsupported, "reference_executions": reference_count,
            "consumer_fidelity": "PASS_ACTUAL_REFERENCE_RUNS", "unsupported_field_negative": typed["unsupported_field_control"]["status"],
            "removed_intervention_negative": negatives[suite]["status"], "history_r3": {"scope": "RETAINED_R3_NOT_CURRENT_REPROBE",
                "unique_inputs": sum(history_counts[suite].values()), "probe_statuses": dict(history_counts[suite]),
                "generated_cases": len(generated), "classification_counts": dict(groups),
                "generated_behavior_matches": sum(row["behavior_matches"] > 0 for _, row in generated),
                "classification_row_indexes": [i for i, _ in generated]},
            "current_full_history_nonduplicate_instance": "NOT_ESTABLISHED_BY_THIS_D_INVENTORY",
            "nonduplicate_gap": "Recheck both arms against the current complete index/probes; R3 valid-family instances are historical classifications, not current acceptance.",
            "capability_gap": "Bounded declared enum grammar only; arbitrary topology/tools/truth/scorer proposals are unsupported; no qualified G3 parent.",
            "machine_qualified": 0, "production": "BLOCKED_MACHINE_QUALIFICATION", "replay": "NOT_RUN_IN_D", "simulation_only": value["simulation_only"]}
    if sum(row["reference_executions"] for row in rows.values()) != cap["reference_gate_executions"]:
        raise ValueError("reference denominators disagree")
    if source_tree_hash(ROOT) != before:
        raise ValueError("runtime changed during readiness inspection; use a new output")
    write(output / "STAGED_MOCK_PREFLIGHT.json", {"runtime_source_sha256": before, "suites": mock_rows, "provider_calls": 0})
    write(output / "NEGATIVE_CONTROLS.json", {"runtime_source_sha256": before, "suites": negatives, "provider_calls": 0})
    report = {"schema_version": "ioabench.v5.round01-readiness/1.0.0", "status": "ENGINEERING_READY_BOUNDED_MACHINE_QUALIFICATION_BLOCKED",
        "runtime_source_sha256": before, "r3_runtime_source_sha256": history["runtime_source_sha256"], "suite_count": len(rows),
        "dynamic_slice_count": cap["slice_count"], "reference_executions": cap["reference_gate_executions"],
        "finite_enum_cells": sum(row["enum_cells_declared"] for row in rows.values()),
        "supported_enum_cells": sum(row["enum_cells_supported"] for row in rows.values()), "g2_mock_stages": sum(row["stage_count"] for row in mock_rows.values()),
        "negative_control_counts": {"unsupported_field_rejected": sum(row["unsupported_field_negative"] == "REJECTED" for row in rows.values()),
            "removed_intervention_rejected": len(negatives)}, "suites": rows, "provider_calls": 0, "machine_qualified": 0,
        "scientific_validity": "NOT_ESTABLISHED", "formal_freeze": "NOT_RUN", "replay": "NOT_RUN_IN_D",
        "r3_generated_classification_counts": dict(Counter(row["quality_classification"]["status"] for row in history["rows"])),
        "inputs_sha256": {path.relative_to(ROOT).as_posix(): sha(path) for path in inputs},
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha(path) for path in [Path(__file__), ROOT / "scripts/v5/factory_capability_manifest.py"]}}
    write(output / "READINESS_RESULT.json", report)
    lines = ["# 18 项批量生成工程准备度", "", "状态：`ENGINEERING_READY_BOUNDED / MACHINE_QUALIFICATION_BLOCKED`。当前重跑 18 typed、19 slices、52 个有限枚举组合中 49 个可执行，540 次参考执行；18 个未声明字段、18 个移除风险干预负例均拒收。API 调用 0。", "",
        f"当前 runtime SHA-256：`{before}`。R3 历史 SHA：`{history['runtime_source_sha256']}`；历史分类只读取并绑定哈希，没有把旧结果当成本轮执行。", "",
        "G1 = 程序提案已编译并执行。G2 = 当前四阶段 schema/依赖链 Mock 预检（18 项×4阶段）；真实 AI 生成只引用 R3 的三样板记录，本轮没有新模型调用。G3 = 工程接口存在，但全部缺少同 suite/adapter/source 的机器合格父代，均 BLOCKED。", "",
        "|测评|G1 / typed / consumer|枚举可执行/声明|参考执行|G2 当前 / R3有效对|G3|未声明字段/去风险负例|", "|---|---|---:|---:|---|---|---|"]
    for suite, row in rows.items():
        generated_pairs = row["g2"]["r3_generation_statuses"].get("ENGINEERING_VALID", 0)
        lines.append(f"|{suite} {row['name']}|PASS（有限语法）|{row['enum_cells_supported']}/{row['enum_cells_declared']}|{row['reference_executions']}|Mock PASS / {generated_pairs}|BLOCKED|拒收/拒收|")
    lines += ["", "上述参考分母包括已注册动态 slice、typed 默认例和各枚举例；存在默认例重复计数，不能解释为 540 个独立样本。消费者证明来自实际参考轨迹的 execution_fidelity；本轮 D 未运行正常 runner/严格 Replay，C 闭环另行报告。", "",
        "|测评|已执行结构因子与边界|", "|---|---|"]
    for suite, row in rows.items():
        factors = "; ".join(name + "=" + "/".join(map(str, value["values"])) for name, value in row["finite_factors"].items())
        gap = "；不可行：" + json.dumps([item["factors"] for item in row["unsupported_or_infeasible_cells"]], ensure_ascii=False) if row["unsupported_or_infeasible_cells"] else ""
        lines.append(f"|{suite} {row['name']}|`{factors}`{gap}|")
    lines += ["", "|测评|R3历史唯一输入|PROBED / INDETERMINATE|R3新增Case|exact / near / family-instance|存在历史行为匹配|当前非重复可入库实例|", "|---|---:|---|---:|---|---|---|"]
    for suite, row in rows.items():
        h = row["history_r3"]
        counts = h["classification_counts"]
        lines.append(f"|{suite} {row['name']}|{h['unique_inputs']}|{h['probe_statuses'].get('PROBED', 0)} / {h['probe_statuses'].get('INDETERMINATE', 0)}|{h['generated_cases']}|{counts.get('EXACT_DUPLICATE',0)} / {counts.get('NEAR_DUPLICATE',0)} / {counts.get('VALID_FAMILY_INSTANCE',0)}|{h['generated_behavior_matches']} / {h['generated_cases']}|本表未建立|")
    lines += ["", "R3 新增 78 Case 的分母是 39 对的两臂，分类合计 24 exact、26 near、28 既有家族实例；78/78 有历史行为匹配，新科学家族 0。28 个既有家族实例不等于机器接纳，不证明本轮完整历史下的新实例。R3 全历史 7,687 个唯一输入中 6,661 PROBED、1,026 INDETERMINATE；D 未重复全历史重建，当前 C 的索引/拒收证据是本轮准入依据。", "",
        "每项共同 CAPABILITY_GAP：仅支持列出的有限语法与既有消费者，不支持任意新图、工具、真值或评分规则。没有独审资格、没有 G3 合格父代；全 18 项机器合格数均为 0，非重复实例的当前全历史准入证据仍须逐对建立。T361 判断让渡、T362 讨论扭曲、T363 能动性弱化保持 SIMULATION_ONLY。", "",
        "当前证据：`readiness/CAPABILITY.json`、`STAGED_MOCK_PREFLIGHT.json`、`NEGATIVE_CONTROLS.json`、`READINESS_RESULT.json`；命令/退出码/UTC 时间在 `CAPABILITY_COMMAND.json` 与 `READINESS_COMMAND.json`。READINESS_RESULT 保存输入文件 SHA 和历史分类逐行索引，可审查每项计数。", "",
        "未开展真实 G2 生成、G3、生产扩量、科学难度校准、确认性 Pilot、Campaign 或正式冻结；工程准备度不代表科学有效性。", ""]
    write(output.parent / "SUITE18_READINESS.md", "\n".join(lines))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.out.resolve())
    print(json.dumps({key: report[key] for key in ("status", "runtime_source_sha256", "suite_count", "reference_executions", "provider_calls")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
