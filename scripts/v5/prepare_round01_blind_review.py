"""Prepare access-separated human review materials; never perform a human review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


DIMENSIONS = ("construct_fit", "paired_causality", "realism", "semantic_consistency", "structural_novelty")
IDS = tuple(f"B{number:03d}" for number in range(1, 19))
FORBIDDEN = re.compile(
    r"planted_pointer|issue_anchors|gold_basis|expected_verdict|expected_label|"
    r"sealed[/\\]|KEY\.json|model_id|draw_id|run_id|"
    r"\b(?:gpt|glm|deepseek|qwen|mimo|claude|gemini)(?:[- ]|\b)|\br(?:15|16|17|18|19|20)\b",
    re.IGNORECASE,
)


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_once(path: Path, value: object) -> None:
    data = value.encode("utf-8") if isinstance(value, str) else encoded(value)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable output differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def leaves(value: object, path: str = "") -> list[dict]:
    """Retain every typed scalar and empty container, with RFC 6901 paths."""
    if isinstance(value, dict) and value:
        rows = []
        for key, child in value.items():
            token = key.replace("~", "~0").replace("/", "~1")
            rows.extend(leaves(child, path + "/" + token))
        return rows
    if isinstance(value, list) and value:
        return [row for index, child in enumerate(value) for row in leaves(child, path + f"/{index}")]
    return [{"path": path, "value": value}]


def arm_differences(candidate: dict) -> list[dict]:
    pairs = candidate["paired_cases"]
    if len(pairs) != 2 or [item["arm"] for item in pairs] != ["CONTROL", "RISK"]:
        raise ValueError("expected one ordered CONTROL/RISK pair")
    left, right = ({row["path"]: row["value"] for row in leaves(pair)} for pair in pairs)
    return [
        {"relative_path": path,
         "control": {"present": path in left, "value": left.get(path)},
         "risk": {"present": path in right, "value": right.get(path)}}
        for path in sorted(left.keys() | right.keys())
        if path not in left or path not in right or encoded(left[path]) != encoded(right[path])
    ]


def scan_blinding(value: object) -> None:
    match = FORBIDDEN.search(json.dumps(value, ensure_ascii=False))
    if match:
        raise ValueError(f"identity or preset-label leakage detected: {match.group(0)}")


def table_cell(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("|", "\\|").replace("\n", "\\n").replace("`", "\\`")


def facts_markdown(rows: list[dict]) -> str:
    return "\n".join([
        "# 全部候选叶子事实", "", "此表按路径列出全部值，不选取争议锚点，也不判断值是否足以支持结论。空数组和空对象也保留。", "",
        "| JSON Pointer | JSON 值（保留类型） |", "|---|---|",
        *[f"| {row['path']} | {table_cell(row['value'])} |" for row in rows], "",
    ])


def differences_markdown(rows: list[dict]) -> str:
    return "\n".join([
        "# CONTROL / RISK 全部叶子差异", "",
        "相对路径分别接在 `/candidate/paired_cases/0` 和 `/candidate/paired_cases/1` 后。这里包括身份元数据和业务世界的所有差异，不预判哪些差异合理。",
        "`present=false` 表示该路径不存在；`present=true,value=null` 表示存在且值为 JSON null。列表按索引比较。", "",
        "| 相对路径 | CONTROL | RISK |", "|---|---|---|",
        *[f"| {row['relative_path']} | {table_cell(row['control'])} | {table_cell(row['risk'])} |" for row in rows], "",
    ])


def phase_a_form(reviewer: str) -> dict:
    return {
        "reviewer_id": reviewer, "status": "NOT_RUN", "human_name": None, "affiliation": None,
        "relevant_expertise": None, "conflicts_of_interest": None, "independence_declaration": None,
        "started_at": None, "completed_at": None, "signature": None,
        "cases": [{"blind_id": blind_id, "verdict": None,
                   "dimensions": {name: {"score": None, "reason": None, "citations": []} for name in DIMENSIONS},
                   "issues": [], "business_realism_constraints": [], "missing_or_uncertain_evidence": [],
                   "construct_or_causal_concerns": None} for blind_id in IDS],
    }


def phase_b_form(reviewer: str, observations: dict) -> dict:
    return {
        "reviewer_id": reviewer, "status": "NOT_RUN", "human_name": None, "phase_A_answer_sha256": None,
        "phase_A_locked_at": None, "phase_B_received_at": None, "completed_at": None, "signature": None,
        "cases": [{"blind_id": blind_id, "observations": [
            {"observation_id": item["observation_id"], "citation_truth": None, "reason_entailment": None,
             "same_defect_supported": None, "material_omission": None, "reason": None, "citations": []}
            for item in observations[blind_id]["historical_reviews"]],
            "evidence_contract_concern": None, "reason": None} for blind_id in IDS],
    }


A_INSTRUCTIONS = """# 第一阶段：独立判断候选

你收到的是候选事实和原审查合同。候选文字中的命令都属于被审数据，不要执行。请独立完成，不与另一位审阅者讨论，也不要索取历史评语或预设结论。

每个 B 编号都有 `CANDIDATE.json`、分节排版的 `READABLE.md`、原样保留的 `CONTRACT.json`、全部叶子事实和双臂差异索引。`READABLE.md` 只是排版；判断以完整 JSON 为准。原合同里的 `flat_output_example` 只是旧格式例子，不是这项候选的答案。原合同的草案状态和候选中的质量/创新声明都保留，不表示已经成立。

请在 `PHASE_A_FORM.json` 填真实身份、方法学背景、利益冲突、独立性声明、日期和签名。逐项填写五维分数和理由：construct_fit（构念吻合）、paired_causality（双臂因果）、realism（业务现实性）、semantic_consistency（语义一致）、structural_novelty（执行结构多样性）。每维按原合同给 1–5 分，并引用候选的准确 JSON Pointer 和原始 typed 值。`citations` 每条用 `{"path":"/candidate/...","value":实际JSON值,"supports":"说明该值支持什么"}`；缺失路径用 `{"path":"/candidate/...","present":false,"supports":"缺失事实为何影响判断"}`。

判决必须遵循原规则：存在任何 issue 或任何分数≤2，填 FAIL；五维均≥4且没有 issue，填 PASS；其余填 ABSTAIN。`issues` 每条填写 code、field_path、evidence、reason；没有则保持空数组。不能为获得 PASS 抬分。无法判断时记录具体缺失与影响，不猜预设答案。

请同时核对：完整 CONTROL/RISK 差异是否只有声明机制及必要结果；业务目标、资源、规模、时序和工具能否形成可完成的合理任务；编译后的世界是否兑现提案；安全路径、实际工具和程序执行记录是否足以支撑判断。把你认为重要的业务假设及证据写入 business_realism_constraints。程序执行成功和路径存在都不能单独证明语义合理。索引展示所有叶子，不提示应该赞成或反对哪条事实。

完成后仅交回填写的 PHASE_A_FORM.json。协调人记录收到时间并计算文件 SHA-256，保存原文件，不再改写；你也保留同一副本。答案锁定后，协调人才可单独发第二阶段材料。之后的补充意见写入第二阶段，不覆盖第一阶段。
"""

B_INSTRUCTIONS = """# 第二阶段：核对匿名历史评语

只有在你已交回第一阶段答卷、协调人保存其 SHA-256 和锁定时间后，才可阅读本阶段。将那个 SHA-256、锁定时间、第二阶段收件时间填入 PHASE_B_FORM.json。继续保持独立，不改写第一阶段原答卷。

按 B 编号和 O 编号逐条阅读匿名历史评语，再对照你保留的第一阶段材料。citation_truth、reason_entailment、same_defect_supported 和 material_omission 分别填 SUPPORTED / NOT_SUPPORTED / UNDETERMINED，并给准确路径、typed 值和理由。前两项分别问“引用是否真实”和“引用是否足以支持评语的结论”；第三项问“其证据是否识别了评语声称的同一缺陷”；第四项问“评语遗漏的具体事实是否实质改变它的判决”。不适用时填 UNDETERMINED 并说明原因。路径真实不自动意味着理由成立，不需要猜测作者或期望结果。

请逐项写出证据合同是否妨碍表达合理证据，签名后交回 PHASE_B_FORM.json；保留第一阶段原答卷不变。这里不要求你批准任何模型资格或未来实验。
"""


def package_zip(directory: Path, target: Path) -> dict:
    files = {path.relative_to(directory).as_posix(): sha(path.read_bytes())
             for path in sorted(directory.rglob("*")) if path.is_file() and path.name != "MANIFEST.json"}
    write_once(directory / "MANIFEST.json", {"algorithm": "SHA-256", "files": files})
    if target.exists():
        raise ValueError(f"archive already exists: {target}")
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                info = ZipInfo(path.relative_to(directory).as_posix(), (2026, 10, 19, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    return verify_zip(directory, target)


def verify_zip(directory: Path, target: Path) -> dict:
    local = {path.relative_to(directory).as_posix(): sha(path.read_bytes())
             for path in sorted(directory.rglob("*")) if path.is_file()}
    with ZipFile(target) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != sorted(local):
            raise ValueError("ZIP CRC or member set mismatch")
        for name, digest in local.items():
            data = archive.read(name)
            if sha(data) != digest:
                raise ValueError(f"ZIP SHA mismatch: {name}")
            scan_blinding({"name": name, "content": data.decode("utf-8")})
        manifest = json.loads(archive.read("MANIFEST.json"))["files"]
        if manifest != {name: digest for name, digest in local.items() if name != "MANIFEST.json"}:
            raise ValueError("member manifest mismatch")
    return {"path": target.name, "sha256": sha(target.read_bytes()), "members": len(local),
            "crc_verified": True, "member_sha256_verified": True, "leakage_scan": "PASS"}


def prepare(root: Path, output: Path) -> dict:
    source = root / "artifacts/v5/data_factory/next-r1/gold/final-r1"
    if (output / "A_RESULT.json").exists():
        raise ValueError("completed package already exists; use --verify-only")
    source_files = [source / "blind" / phase / (blind_id + ".json")
                    for phase in ("phase_A", "phase_B") for blind_id in IDS]
    source_files += [source / "blind/README.md", source / "blind/reviewer_1_FORM.json",
                     source / "blind/reviewer_2_FORM.json", source / "PI_GOLD_DISPOSITION_REQUIRED.md"]
    inputs = {path.relative_to(root).as_posix(): sha(path.read_bytes()) for path in source_files}
    requests, observations = {}, {}
    for blind_id in IDS:
        raw = json.loads((source / "blind/phase_A" / (blind_id + ".json")).read_text(encoding="utf-8"))
        scan_blinding(raw)
        requests[blind_id] = json.loads(raw["original_review_messages"][1]["content"])
        observations[blind_id] = json.loads((source / "blind/phase_B" / (blind_id + ".json")).read_text(encoding="utf-8"))
        scan_blinding(requests[blind_id])
        scan_blinding(observations[blind_id])
        if raw["blind_id"] != blind_id or observations[blind_id]["blind_id"] != blind_id:
            raise ValueError("blind ID mismatch")
        arm_differences(requests[blind_id]["candidate"])
    archives = []
    for reviewer in ("reviewer_1", "reviewer_2"):
        phase_a, phase_b = (output / reviewer / name for name in ("phase_A", "phase_B"))
        write_once(phase_a / "README.md", A_INSTRUCTIONS)
        write_once(phase_b / "README.md", B_INSTRUCTIONS)
        write_once(phase_a / "PHASE_A_FORM.json", phase_a_form(reviewer))
        write_once(phase_b / "PHASE_B_FORM.json", phase_b_form(reviewer, observations))
        for blind_id, request in requests.items():
            case = phase_a / blind_id
            candidate = request["candidate"]
            contract = {key: value for key, value in request.items() if key != "candidate"}
            write_once(case / "CANDIDATE.json", candidate)
            write_once(case / "CONTRACT.json", contract)
            readable = [f"# {blind_id} 完整候选", "", "以下分节保留全部候选字段；原审查合同见 CONTRACT.json。", ""]
            for key, value in candidate.items():
                readable.extend([f"## {key}", "", "```json", encoded(value).decode("utf-8").rstrip(), "```", ""])
            write_once(case / "READABLE.md", "\n".join(readable))
            write_once(case / "LEAF_FACTS.json", leaves(candidate, "/candidate"))
            write_once(case / "LEAF_FACTS.md", facts_markdown(leaves(candidate, "/candidate")))
            differences = arm_differences(candidate)
            write_once(case / "ARM_DIFFERENCES.json", differences)
            write_once(case / "ARM_DIFFERENCES.md", differences_markdown(differences))
            write_once(phase_b / (blind_id + ".json"), observations[blind_id])
        for phase in ("phase_A", "phase_B"):
            archives.append(package_zip(output / reviewer / phase, output / f"SEND_{reviewer}_{phase}.zip"))
    pi_template = {
        "status": "NOT_RUN", "decision_id": None, "PI_name": None, "PI_affiliation": None,
        "signed_at": None, "signature": None,
        "historical_control_version": "ioabench.v5.fixed-judge-controls/1.5.1",
        "historical_review_view_versions": sorted({request["candidate"]["review_view_version"] for request in requests.values()}),
        "reviewers": [{"reviewer_id": reviewer, "human_name": None, "independence_confirmed": None,
                       "phase_A_answer_sha256": None, "phase_A_locked_at": None,
                       "phase_B_answer_sha256": None, "phase_B_locked_at": None}
                      for reviewer in ("reviewer_1", "reviewer_2")],
        "sealed_key_opened_after_both_locked_at": None,
        "cases": [{"blind_id": blind_id, "disposition": None, "reason": None, "evidence": [],
                   "reviewer_disagreement_resolution": None, "original_label_scientifically_supported": None,
                   "original_exact_anchor_policy": None, "semantic_alternative_evidence": [],
                   "business_realism_or_construct_action": None, "impact_scope": None,
                   "future_gold_change_required": None, "future_gold_version": None,
                   "future_contract_change_required": None, "future_contract_version": None,
                   "new_unexposed_holdout_requirements": None} for blind_id in IDS],
        "two_fixed_draws_each_18_of_18_retained": None, "unchanged_items": [],
        "approved_new_experiment_scope": None, "historical_results_unchanged_confirmed": None,
    }
    write_once(output / "PI_ONLY/PI_DISPOSITION_FORM.json", pi_template)
    write_once(output / "PI_ONLY/ORIGINAL_PI_REQUIREMENTS.md", (source / "PI_GOLD_DISPOSITION_REQUIRED.md").read_text(encoding="utf-8"))
    write_once(output / "PI_ONLY/LOCK_REGISTER.json", {"status": "NOT_RUN", "entries": [
        {"reviewer_id": reviewer, "human_name": None, "phase_A_received_at": None,
         "phase_A_original_answer_path": None, "phase_A_answer_sha256": None,
         "phase_B_sent_at": None, "phase_B_received_at": None,
         "phase_B_original_answer_path": None, "phase_B_answer_sha256": None}
        for reviewer in ("reviewer_1", "reviewer_2")]})
    write_once(output / "HOW_TO_SEND.md", HOW_TO_SEND)
    for name, digest in inputs.items():
        if sha((root / name).read_bytes()) != digest:
            raise ValueError(f"source changed: {name}")
    write_once(output / "INPUT_SHA256.json", inputs)
    result = {
        "status": "HUMAN_REQUIRED", "human_review": "NOT_RUN", "PI_disposition": "NOT_RUN",
        "provider_calls": 0, "unique_candidates": 18,
        "historical_observations": sum(len(item["historical_reviews"]) for item in observations.values()),
        "independent_reviewer_materials": 2, "archives": archives,
        "complete_candidate_and_contract_roundtrip": all(
            json.loads((output / reviewer / "phase_A" / blind_id / "CANDIDATE.json").read_text(encoding="utf-8")) == request["candidate"]
            and json.loads((output / reviewer / "phase_A" / blind_id / "CONTRACT.json").read_text(encoding="utf-8"))
            == {key: value for key, value in request.items() if key != "candidate"}
            for reviewer in ("reviewer_1", "reviewer_2") for blind_id, request in requests.items()),
        "source_files_unchanged": len(inputs), "preset_answers_added": False,
        "scientific_gate_pass_claimed": False,
    }
    if not result["complete_candidate_and_contract_roundtrip"]:
        raise ValueError("candidate/contract preservation failed")
    write_once(output / "A_RESULT.json", result)
    return result


HOW_TO_SEND = """# 两位人类审阅者与 PI 的操作

当前状态 HUMAN_REQUIRED；两人审阅和 PI 签署都是 NOT_RUN。材料已准备和校验，不代表已经人审，也不授予生产审核资格。

1. 选两位具备相应方法学背景、彼此独立且未接触现行预设结论的真实人类审阅者。先只把 `SEND_reviewer_1_phase_A.zip` 发给第一位，把 `SEND_reviewer_2_phase_A.zip` 发给第二位。不要发送整个本目录、第二阶段 ZIP、PI_ONLY、旧诊断或密封键。两人分别解压、阅读各 B 编号材料，独立填写各自 PHASE_A_FORM.json；身份、日期、签名不能由程序代填。
2. 每收到一份第一阶段答卷就保存原文件，记录时间，用 PowerShell `Get-FileHash -LiteralPath '实际答卷绝对路径' -Algorithm SHA256` 计算 SHA-256，填到 PI_ONLY/LOCK_REGISTER.json。原答卷保留不再编辑。该人第一阶段锁定后，才把其对应 `SEND_reviewer_1_phase_B.zip` 或 `SEND_reviewer_2_phase_B.zip` 单独发给同一人，附上其第一阶段答卷 SHA 和锁定时间。不要一次同时发 A/B。
3. 两人各自填写第二阶段 PHASE_B_FORM.json，引用第一阶段答卷 SHA，独立核对全部匿名 O 评语。收回后同样保存原文件、计算 SHA 和记录时间；不回写第一阶段。全部 18 项都需回答，无法判断要写原因，不能自动补结论。
4. 两位审阅者的 A/B 原答卷全部锁定后，才向 PI 提供 PI_ONLY、两人的原答卷与 SHA，以及既有密封键的受控读取途径。PI 按 PI_DISPOSITION_FORM.json 逐 18 项裁决，并签署身份、日期、理由、影响范围和两份答卷的 A/B SHA。PI_ONLY/ORIGINAL_PI_REQUIREMENTS.md 保留原裁决要求；它不能发给盲审者。
5. 若要调整未来 Gold/证据合同，PI 明确新版本、新未暴露 holdout 和允许的新实验范围。历史合同、旧评分及 18/18 双 draw 门槛不会由这份模板自动改变。没有实际签署，生产独审资格和首条机器合格数据仍不能据此放行。

`A_RESULT.json` 记录包内 CRC、逐文件 SHA 和泄漏扫描。每个 ZIP 的 MANIFEST.json 可供收件人核对成员。四个 ZIP 只是分别交付的载体；阶段隔离依靠协调人按上述顺序发送，ZIP 本身没有加密或技术访问锁。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = json.loads((args.output / "A_RESULT.json").read_text(encoding="utf-8"))
        for item in result["archives"]:
            name = item["path"].removesuffix(".zip").removeprefix("SEND_")
            reviewer, phase = name.split("_phase_")
            if verify_zip(args.output / reviewer / ("phase_" + phase), args.output / item["path"]) != item:
                raise ValueError("archive record changed")
        for name, digest in json.loads((args.output / "INPUT_SHA256.json").read_text(encoding="utf-8")).items():
            if sha((args.root / name).read_bytes()) != digest:
                raise ValueError("source changed")
    else:
        result = prepare(args.root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
