"""Recompute closed R13 judge evidence and prepare an unadjudicated, blinded PI package."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.judge_controls import score_control, summarize_controls
from ioabench.v5.ai_generation.quality import review_prompt
from ioabench.v5.core.case import resolve_pointer

VERSION = "ioabench.v5.r13-gold-diagnosis/1.0.0"
SETTLEMENT = "artifacts/v5/data_factory/upgrade-20261019/FINAL_AUDITOR_QUALIFICATION_R12.json"
DEFAULT_OUT = "artifacts/v5/data_factory/next-r1/gold/final-r1"
DIMENSIONS = ("construct_fit", "paired_causality", "semantic_consistency", "realism", "structural_novelty")
CATEGORIES = (
    "TRUE_MODEL_FALSE_ACCEPT", "TRUE_MODEL_FALSE_REJECT", "ABSTAIN_FOR_VALID_UNCERTAINTY",
    "JSON_OR_PROTOCOL_ERROR", "TRUNCATION", "FACTUAL_ASSERTION_ERROR",
    "VALID_EVIDENCE_BUT_NARROW_ANCHOR", "GOLD_AMBIGUITY", "CONSTRUCT_OR_CASE_INVALIDITY",
    "EVIDENCE_DOES_NOT_ESTABLISH_PLANTED_DEFECT", "MATCHES_FROZEN_CONTRACT", "NOT_RUN",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, value) -> None:
    data = (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"immutable output differs; choose a new directory: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def cited_facts(view: dict, review: dict, values: dict) -> list[dict]:
    """Check typed values, separately from the scientific entailment of a reason."""
    citations = []

    def add(location, pointer, expected=None, assertion=False):
        row = {"review_location": location, "cited_path": pointer, "citation_true": False}
        try:
            if not isinstance(pointer, str):
                raise ValueError("citation must be a JSON pointer string")
            value = resolve_pointer({"candidate": view}, pointer)
            digest = canonical_sha256(value)
            values[digest] = value
            row.update(citation_true=True, actual_value_sha256=digest,
                       actual_value_ref=f"FACT_VALUES.json#/{digest}")
            if not isinstance(value, (dict, list)):
                row["actual_value"] = value
            if assertion:
                row.update(asserted_value=expected, assertion_true=canonical_sha256(expected) == digest)
        except (KeyError, IndexError, TypeError, ValueError):
            if assertion:
                row.update(asserted_value=expected, assertion_true=False)
        citations.append(row)

    for dimension in DIMENSIONS:
        item = review.get(dimension, {})
        if not isinstance(item, dict):
            continue
        for index, pointer in enumerate(item.get("evidence", [])):
            add(f"/{dimension}/evidence/{index}", pointer)
        for index, assertion in enumerate(item.get("assertions", [])):
            if isinstance(assertion, dict):
                add(f"/{dimension}/assertions/{index}", assertion.get("path"), assertion.get("equals"), True)
        for index, observation in enumerate(item.get("observations", [])):
            for offset, pointer in enumerate(observation.get("evidence", [])):
                add(f"/{dimension}/observations/{index}/evidence/{offset}", pointer)
    for index, issue in enumerate(review.get("issues", [])):
        for field in ("field_path", "evidence"):
            add(f"/issues/{index}/{field}", issue.get(field))
    return citations


def classify(control: dict, score: dict | None, facts: list[dict], *, finish_reason=None) -> list[str]:
    if finish_reason == "length":
        return ["TRUNCATION"]
    if score is None:
        return ["NOT_RUN"]
    categories = []
    expected, verdict = control["expected"], score.get("verdict")
    if expected != "PASS" and verdict == "PASS":
        categories.append("TRUE_MODEL_FALSE_ACCEPT")
    elif expected == "PASS" and verdict == "FAIL":
        categories.append("TRUE_MODEL_FALSE_REJECT")
    elif expected != verdict:
        categories.append("GOLD_AMBIGUITY" if expected == "PASS" and verdict == "ABSTAIN"
                          else "JSON_OR_PROTOCOL_ERROR")
    if expected == verdict == "ABSTAIN":
        categories.append("ABSTAIN_FOR_VALID_UNCERTAINTY")
    findings = score.get("findings", [])
    if any(fact.get("assertion_true") is False for fact in facts):
        categories.append("FACTUAL_ASSERTION_ERROR")
    if findings:
        categories.append("JSON_OR_PROTOCOL_ERROR")
    if not score.get("supported_issue") and expected == verdict == "FAIL":
        # A true pointer alone does not prove the reviewer noticed the planted defect.
        injection_only = control["id"] == "T321-injection"
        issue_facts = [fact for fact in facts if fact["review_location"].startswith("/issues/")]
        categories.append("VALID_EVIDENCE_BUT_NARROW_ANCHOR" if not injection_only and issue_facts
                          and all(fact["citation_true"] for fact in issue_facts)
                          else "EVIDENCE_DOES_NOT_ESTABLISH_PLANTED_DEFECT")
    if not categories:
        categories.append("MATCHES_FROZEN_CONTRACT")
    return list(dict.fromkeys(categories))


def bound_records(value):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value
        for item in value.values():
            yield from bound_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from bound_records(item)


def build(root: Path, out: Path) -> dict:
    inputs = {}

    def read(path):
        path = root / path
        inputs[path.relative_to(root).as_posix()] = sha(path)
        return json.loads(path.read_text(encoding="utf-8"))

    settlement = read(SETTLEMENT)
    if not settlement["finite_comparison_closed"] or settlement["qualified_auditors"]:
        raise ValueError("this diagnosis is only for the closed, unqualified R13 comparison")
    for record in bound_records(settlement):
        path = root / record["path"]
        actual = sha(path)
        if actual != record["sha256"]:
            raise ValueError(f"original bound evidence changed: {record['path']}")
        inputs[record["path"]] = actual
    rows, draws, values, controls_by_id, observations = [], {}, {}, {}, {}
    for run_id, original in settlement["draws"].items():
        run = Path("artifacts/v5/data_factory/quality_controls") / run_id
        contract = read(run / "CONTROL_CONTRACT.json")
        # Recompute only with byte-identical original scoring code, never silently rejudge.
        for name in ("src/ioabench/v5/ai_generation/judge_controls.py", "src/ioabench/v5/ai_generation/quality.py"):
            if sha(root / name) != contract["source"][name]:
                raise ValueError(f"original scoring source differs: {name}; use the archived environment")
            inputs[name] = sha(root / name)
        controls = read(run / "GOLD_CONTROLS.json")
        if canonical_sha256(controls) != contract["controls_sha256"]:
            raise ValueError("original Gold binding mismatch")
        progress = read(run / ("CONTROL_RESULT.json" if (root / run / "CONTROL_RESULT.json").exists() else "CONTROL_PROGRESS.json"))
        saved_scores = {row["id"]: row for row in progress["rows"]}
        valid_scores = []
        for ordinal, control in enumerate(controls, 1):
            ident = control["id"]
            if ident in controls_by_id and controls_by_id[ident] != control:
                raise ValueError("fixed control differs between draws")
            controls_by_id[ident] = control
            directory = run / ident
            response = read(directory / "AUDITOR_RESPONSE.json") if (root / directory / "AUDITOR_RESPONSE.json").exists() else None
            review = read(directory / "REVIEW.json") if (root / directory / "REVIEW.json").exists() else None
            finish = response.get("finish_reason") if response else None
            score = score_control(control, review) if review is not None and finish != "length" else None
            if score is not None:
                if score != saved_scores[ident]:
                    raise ValueError(f"original score not reproduced: {run_id}/{ident}")
                valid_scores.append(score)
            elif response is not None and finish != "length":
                raise ValueError("unclassified saved response; explicit diagnosis required")
            facts = cited_facts(control["view"], review, values) if review else []
            categories = classify(control, score, facts, finish_reason=finish)
            issue_anchors = control.get("issue_anchors", {}).get("alternatives")
            if issue_anchors is None and control.get("planted_pointer"):
                issue_anchors = [{"legacy_membership": "field_path OR evidence equals planted_pointer",
                                 "planted_pointer": control["planted_pointer"]}]
            row = {"run_id": run_id, "model_id": original["model_id"], "case_id": ident, "ordinal": ordinal,
                   "design_construct": control["view"]["blueprint"].get("suite_id"),
                   "ground_truth_source": {"path": (run / "GOLD_CONTROLS.json").as_posix(),
                       "gold_basis": control["gold_basis"], "input_sha256": canonical_sha256(control["view"]),
                       "machine_validation": control.get("machine_validation"),
                       "hard_gate_sha256": control.get("hard_gate_sha256")},
                   "expected_verdict": control["expected"], "expected_evidence_anchors": issue_anchors or [],
                   "observed_verdict": score.get("verdict") if score else None,
                   "original_score_recomputed": score, "categories": categories,
                   "cited_facts": facts, "issues": review.get("issues", []) if review else [],
                   "dimension_assessments": {name: review[name] for name in DIMENSIONS if name in review} if review else {},
                   "scores": {name: review[name].get("score") for name in DIMENSIONS if isinstance(review.get(name), dict)} if review else {},
                   "semantic_support": "PI_REQUIRED_FOR_SCIENTIFIC_ENTAILMENT" if not score or not score["correct"] else "FROZEN_CONTRACT_MATCH_ONLY_NOT_HUMAN_VALIDATION",
                   "reason": "Exact frozen score, typed citation truth and original outcome are recomputed separately; semantic entailment and positive realism remain independently adjudicable.",
                   "finish_reason": finish, "usage": response.get("usage") if response else None,
                   "review_evidence": (directory / "REVIEW.json").as_posix() if review else None,
                   "response_evidence": (directory / "AUDITOR_RESPONSE.json").as_posix() if response else None,
                   "status": "PASS" if score and score["correct"] else "NOT_RUN" if not response else "FAIL"}
            rows.append(row)
            if review:
                observations.setdefault(ident, []).append({"run_id": run_id, "model_id": original["model_id"], "review": review})
        summary = summarize_controls(valid_scores)
        if summary != original["summary_of_valid_judgments"]:
            raise ValueError(f"original draw summary not reproduced: {run_id}")
        draws[run_id] = {"model_id": original["model_id"], "recomputed_summary": summary,
                        "saved_responses": sum(row["run_id"] == run_id and row["response_evidence"] is not None for row in rows),
                        "truncated": sum(row["run_id"] == run_id and row["finish_reason"] == "length" for row in rows),
                        "not_run": sum(row["run_id"] == run_id and row["status"] == "NOT_RUN" for row in rows)}
    counts = Counter(category for row in rows for category in row["categories"])
    report = {"schema_version": VERSION, "status": "PASS_FACTUAL_RECOMPUTATION_BLOCKED_PI_DISPOSITION",
              "provider_calls": 0, "original_scores_labels_anchors_changed": False,
              "unique_controls": len(controls_by_id), "control_draw_rows": len(rows),
              "draws": draws, "categories": {name: counts[name] for name in CATEGORIES},
              "qualified_auditors": [], "new_auditor_research": "BLOCKED_PI_GOLD_DISPOSITION",
              "rows": rows}
    write_once(out / "FACT_VALUES.json", values)
    write_once(out / "DIAGNOSIS.json", report)
    table = ["# R13 已结束独审比较：逐例事实复算", "", "程序复算通过；科学Gold/锚点裁决仍BLOCKED。引用路径存在不等于语义支持。原结果不重判。", "",
             "| draw | case | expected | observed | frozen正确 | 分类 |", "|---|---|---|---|---|---|"]
    table += [f"| {row['run_id'].rsplit('-', 1)[1]} | {row['case_id']} | {row['expected_verdict']} | {row['observed_verdict'] or row['status']} | {row['original_score_recomputed']['correct'] if row['original_score_recomputed'] else '无有效判断'} | {', '.join(row['categories'])} |" for row in rows]
    write_once(out / "DIAGNOSIS.md", "\n".join(table) + "\n")
    key = {"schema_version": VERSION, "blinding": "access-separated unencrypted key; withhold until two independent reviews are locked", "cases": {}}
    forms = []
    for index, control in enumerate(sorted(controls_by_id.values(), key=lambda item: canonical_sha256(item["view"])), 1):
        blind_id = f"B{index:03d}"
        prompt = review_prompt(control["view"])
        write_once(out / "blind/phase_A" / (blind_id + ".json"), {"blind_id": blind_id, "original_review_messages": prompt})
        anonymized, obs_key = [], {}
        for offset, observation in enumerate(observations.get(control["id"], []), 1):
            obs_id = f"O{offset:02d}"
            anonymized.append({"observation_id": obs_id, "review": observation["review"]})
            obs_key[obs_id] = {name: observation[name] for name in ("run_id", "model_id")}
        write_once(out / "blind/phase_B" / (blind_id + ".json"), {"blind_id": blind_id, "historical_reviews": anonymized})
        key["cases"][blind_id] = {"case_id": control["id"], "expected": control["expected"],
                                  "gold_basis": control["gold_basis"], "anchors": control.get("issue_anchors"),
                                  "planted_pointer": control.get("planted_pointer"), "machine_validation": control.get("machine_validation"),
                                  "mutations": control.get("mutations"), "observations": obs_key}
        forms.append({"blind_id": blind_id, "phase_A": {"verdict": None, "five_scores": {name: None for name in DIMENSIONS},
                      "realism_or_construct_concern": None, "cited_paths_and_values": [], "reason": None},
                      "phase_B": {"observation_entailment": [], "anchor_contract_question": None, "reason": None}})
    write_once(out / "sealed/KEY.json", key)
    for reviewer in ("reviewer_1", "reviewer_2"):
        write_once(out / "blind" / (reviewer + "_FORM.json"), {"reviewer_id": reviewer, "status": "NOT_REVIEWED", "cases": forms})
    write_once(out / "blind/README.md", BLIND_INSTRUCTIONS)
    write_once(out / "PI_GOLD_DISPOSITION_REQUIRED.md", PI_REQUIRED)
    write_once(out / "NEW_AUDITOR_COMPARISON_PREREGISTRATION.json", {
        "schema_version": VERSION, "status": "DRAFT_FROZEN_EXECUTION_BLOCKED_PI_DISPOSITION", "provider_calls": 0,
        "closed_old_controls": "No additional model or draw on the old 18 controls; no old outcome promoted.",
        "candidates": ["gpt-6.1-sol", "glm-5.3-flash", "mimo-v2.6-pro", "claude-haiku-5-5", "mimo-v2.6-flash", "qwen3.8-flash", "deepseek-v4.1-flash-1017", "glm-5.3"],
        "deepseek_1017_scope": "Unrelated isolated development research only; not formal SUT sample selection, independent review or confirmatory calibration without PI approval.",
        "holdout": "NOT_CREATED; PI disposition first, new unexposed independently labeled 18-control set with new gold/review versions.",
        "dimensions": list(DIMENSIONS), "control_coverage": ["valid positives", "planted negatives", "expected ABSTAIN", "complex causality", "realism", "evidence entailment", "truncation negative"],
        "qualification": "Two fixed complete draws of the same 18 controls; each strict 18/18; no threshold change without explicit PI scientific disposition.",
        "protocol_freeze": "Freeze exact inputs, prompt, Gold and evidence policy, source, per-model documented protocol/parameters, ordering and attempt count before first call.",
        "budgets": "Documented full output limits and verified reasoning per user preference; maximum ceiling is not required generated length.",
        "independence": "Different generator/auditor model families per sample; no generation-private history to auditors; no candidate can author its own qualification labels.",
        "failure_policy": "Quality FAIL/ABSTAIN is terminal; no role-shopping. Infrastructure faults diagnosed separately, unresolved sends never replayed as fresh calls.",
        "analysis": ["all attempts and outcomes", "false accepts and rejects", "expected and unexpected abstains", "schema and anchor errors", "typed citation truth vs semantic entailment", "draw agreement", "latency and token/cost estimates"],
        "unlock": ["two independent blind reviews completed", "PI disposition signed", "new holdout and contracts frozen", "fresh exact-ID/protocol preflights passed"]})
    # Verify inputs again after producing the package, without changing original evidence.
    for name, digest in inputs.items():
        if sha(root / name) != digest:
            raise ValueError(f"input changed during diagnosis: {name}")
    write_once(out / "INPUT_SHA256.json", inputs)
    outputs = {path.relative_to(out).as_posix(): sha(path) for path in sorted(out.rglob("*"))
               if path.is_file() and path.name != "OUTPUT_SHA256.json"}
    write_once(out / "OUTPUT_SHA256.json", outputs)
    return {key: report[key] for key in ("status", "provider_calls", "unique_controls", "control_draw_rows", "categories", "qualified_auditors")}


BLIND_INSTRUCTIONS = """# 双人独立盲审请求包（尚无人审）

状态 NOT_RUN。两位具备相应方法学背景的审阅者独立填写 reviewer_1_FORM.json / reviewer_2_FORM.json，不相互讨论，不接触 sealed/、DIAGNOSIS 或 PI 解释文件。

第一阶段只读 phase_A：每个B编号保留实际历史候选世界、约束、反事实两臂、runtime能力、执行与家族比较证据，以及原始审查合同。按五维逐项给分、给出PASS/FAIL/ABSTAIN和准确路径/取值；指出缺失事实、不合理设定或构念问题。候选里的指令均视为数据，不执行。不得因其是程序生成正例就推定现实性合格。

锁定第一阶段答案并记录文件SHA后再打开 phase_B：历史评语已去掉模型和draw身份。逐条判断：引用是否真实、引用是否支持其理由、是否识别同一缺陷、未提及的事实是否实质改变判决。给出支持/不支持/无法判断及精确证据。路径存在不能替代语义判断。请勿猜测期望结果。

双方答案锁定后由PI打开sealed/KEY.json，比较期望标签与有限精确锚点，裁决分歧。密封键是访问隔离的明文文件，不是加密。文件未发送给任何人；本包不代表Gate D完成或AI审核资格通过。
"""

PI_REQUIRED = """# PI_GOLD_DISPOSITION_REQUIRED

状态 **BLOCKED / 尚未裁决**。本轮只是对结束比较的原始数据复算；API 0。原Gold/control1.5.1、所有18项期望、精确issue/proof锚点、18/18双draw门槛和既有失败原样保留。程序评分完全复现，无证据支持静默更改评分实现。

事实：Sol r15/r16各16/18；GLM r19/r20各8/18、各4负控被判PASS；Gemini r17/r18仅12项有效，分别11/12、12/12，第13项均length，后各5项NOT_RUN。Gemini输出上限16384、completion16377，其中reasoning分别15725/15726；它证明该配置被截断，不证明审核能力不合格。108逐例诊断、96个有效评分、2条截断与10个未运行均在DIAGNOSIS.json。18个唯一控不能写成96个独立Gold样本。

解释A（冻结合同）：精确锚点是事前限定的可验证证明，未命中即严格失败；T352正控预设应PASS。按此解释无人具备生产资格，原结果不变。

解释B（待科学裁决）：某些不同引用可能确实支持同一缺陷。Sol capability-gap引用必要条件叶子/缺少工具列表或完整双臂；Sol wrong-construct引用subtype与整个world；Gemini causal-confound引用RISK单个item叶子并叙述两臂计数；GLM timing引用失败诊断的父字段/status，wrong-construct引用库存变化，wording-only引用去重状态与创新声明。这些引用路径真实，但是否足以证明所述结论须独立判断，不能由路径存在直接批准。GLM injection r20仅指出注入指令，不能据此说它识别了Gold植入的broker数量矛盾，另列未证明植入缺陷。Sol r16 T352-positive的realism=3导致ABSTAIN，与五维规则一致；程序参考策略成功不能单独证明语义现实性≥4。

程序能决定：原文件SHA、精确ID/请求配置、finish_reason和tokens、JSON结构/判决分数一致性、引用路径和typed取值、精确锚点成员关系、已保存程序故障诊断、评分复现。程序不能独立决定：某引用是否语义充分、业务世界是否足够真实、正控标签是否科学成立、Gold锚点代表性，以及候选是否可宣称科学新家族。

请PI在双人独立盲审答案锁定后逐项签署：

1. 锚点是否要求保留原有限proof对，或应在未来版本接纳何种同义证据？分别裁决上述case/observation；不要用模型名称决定。
2. T352正控现实性足以要求PASS吗？若存在合理ABSTAIN，哪项具体世界假设需修正？
3. 若Gold、证据合同或正控需修正，批准新gold_version/review_contract_version及新未暴露独立holdout的构造/标签程序；旧记录不重判、不提升资格。
4. 新研究保持两个固定draw、各18/18吗？在没有明确新科学合同前，答案按保持处理。
5. 明确任何构念/案例有效性质疑的影响范围、弃用或新版本处理；不得改原18构念/评分或冻结SUT。

裁决模板：decision_id、PI身份、日期、审阅者两份答案及SHA、逐项A/B/其他决定、理由与证据、影响的Gold/合同新版本、保持不变项、允许的新实验范围。当前签署 **NOT_RUN**。独立人工审查未执行，不能把本包当作完成科研Gate。

影响范围：闭合的6个历史draw只保留原结论；当前所有辅助模型的独审生产资格继续BLOCKED；生成/修复/协议研究可独立推进，但第一条机器合格样本、三套件小批和18项生产扩展仍需合格独审。NEW_AUDITOR_COMPARISON_PREREGISTRATION.json仅为冻结执行方案草案，未创建新holdout、未发资格调用、未授权正式Pilot/Campaign/冻结/真人研究。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / DEFAULT_OUT)
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.out.resolve()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
