"""Settle the auth-blocked Round02 resume using evidence only; never calls a provider."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(Path(__file__).parent)]
from compare_auxiliary_models import read, sha
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.evaluation import atomic_json, writer_lock
from report_round02_comparison import build, attempts, csv_write
from settle_provider_round02 import tests, wilson


def finalize(out):
    totals = build(out)
    stop = read(out / "STOP.json")
    assert stop["category"] == "AUTH/PERMISSION"
    regression = tests(out / "PROVIDER_REGRESSION_R3.xml")
    assert not any(regression[k] for k in ("failures", "errors", "skipped"))
    assert read(out / "PROTECTED_HISTORY.json")["status"] == "PASS"
    assert read(out / "REPLAY_RESUME.json")["port_calls"] == 0
    assert (out / "WRITER_RELEASED.txt").is_file()
    with writer_lock(ROOT / "artifacts/v5/data_factory"):
        pass
    atomic_json(out / "WRITER_RELEASE_VERIFIED.json", {"status": "PASS", "lock_reacquire_and_release": True,
        "note": "The existing lock file remains; the OS byte lock is released."})
    runtime = source_tree_hash(ROOT)
    routing_versions = {}
    for path in out.rglob("AIHUBMIX_ATTEMPTS.jsonl"):
        parts = path.relative_to(out).parts
        phase = parts[2] if parts[0] == "protocols" else parts[0]
        counts = routing_versions.setdefault(phase, Counter())
        counts.update(json.loads(line)["routing_version"] for line in path.read_text(encoding="utf-8").splitlines()
                      if json.loads(line).get("event") == "REQUEST_STARTED")
    atomic_json(out / "ROUTING_VERSION_PROVENANCE.json", {"request_started_versions": routing_versions,
        "final_runtime_sha256": runtime, "quality_binding": read(out / "QUALITY_EXECUTION_BINDING.json"),
        "limitation": "R/P exact full source trees were not snapshotted at execution. Their durable route version, inputs, parameters and responses are retained; final-tree regression does not relabel them as final-tree online reruns."})
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    runtime_files = [p.relative_to(ROOT).as_posix() for top in ("src", "contracts", "config")
                     for p in (ROOT / top).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    source = {name: sha(ROOT / name) for name in sorted(set(tracked) | set(runtime_files)) if (ROOT / name).is_file()
              and name.split("/")[0] in {"src", "scripts", "tests", "state", "docs", "config", "contracts"}}
    atomic_json(out / "SOURCE_MANIFEST.json", {"git_head": head, "baseline_head": read(out / "BASELINE.json")["head"],
        "runtime_sha256": runtime, "files": source, "no_push": True,
        "scientific_contracts_changed": False, "frozen_SUT_changed": False})
    scores = read(out / "SCORECARD_ALL_MODELS.json")
    plan = read(out / "BENCHMARK_TASKSET_FROZEN.json")
    network = read(out / "network-s1/NETWORK_PATH_DIAGNOSIS.json")
    network.update(provider_recovered="NO_AT_END_AFTER_INITIAL_YES", initial_completion="s1-completion/S1_RESULT.json",
        latest_completion_status=401, latest_failure=stop, root_cause="AUTH_OR_PERMISSION_PROVIDER_SIDE_DETAILS_UNRESOLVED",
        user_network_configuration_changed=False,
        historical_rows=[{"origin": "R3", "completion": "HTTP401", "evidence": "artifacts/v5/data_factory/next-r1/AUTH_BLOCKER.md"},
            {"origin": "Round01", "completion": "curl28_NO_HTTP", "evidence": "artifacts/v5/data_factory/coord-round01-20261019T073200Z/PROVIDER_DIAGNOSIS.md"},
            {"origin": "Round02_previous", "completion": "HTTP401", "evidence": "artifacts/v5/provider_benchmark/round02-20261020T002308CST/ROUND_REPORT.md"},
            {"origin": out.name, "completion": "INITIAL_HTTP200_THEN_HTTP401", "evidence": "STOP.json"}])
    atomic_json(out / "NETWORK_PATH_DIAGNOSIS.json", network)
    (out / "NETWORK_PATH_DIAGNOSIS.md").write_text("""# 网络与鉴权事实

主域名DNS成功、直连TCP443超时，TLS未执行；官方备用 api.inferera.com DNS/TCP/TLS1.3/GET成功。本轮首次新MiMo Pro completion HTTP200，身份、JSON与usage120有效，证明当时恢复。未修改系统代理、证书或Key。

质量阶段2026-10-20 03:27:28.947 UTC（北京时间11:27:28.947）再次收到备用地址真实HTTP401；终态为AUTH/PERMISSION，当前恢复状态NO。上游曾成功不代表持续权限。密钥是否再次被禁用、是否账户/渠道/供应商策略导致，无法从现有401确定，需服务方确认。

|时期|DNS/TCP/TLS|GET|新Completion|归因与证据|
|---|---|---|---|---|
|R3历史|UNKNOWN|不证明权限|HTTP401|旧AUTH_BLOCKER.md|
|Round01历史|DNS可解析/TCP失败/TLS未执行|UNKNOWN|curl28，无HTTP|旧PROVIDER_DIAGNOSIS.md|
|Round02前次|备用TCP/TLS成功|成功|HTTP401|原Round02报告|
|本轮开始|备用DNS/TCP/TLS成功|成功|MiMo Pro HTTP200|s1-completion/S1_RESULT.json|
|本轮结束|已有同地址真实HTTP响应|未再查询|Claude Messages HTTP401|STOP.json，wire/http-00766.json|

进程HTTP(S)_PROXY/ALL_PROXY/NO_PROXY未设置；WinHTTP直连；已有WinINET本地HTTP代理127.0.0.1:7897，curl默认不继承该设置。本轮completion走官方备用直连。旧已批准代理比较在原Round02网络证据中，未新建代理或绕路重试。未发现IPv6地址，因此IPv6/TLS该路径NOT_RUN。原始分层结果、时间、证书、curl时序见同名JSON。
""", encoding="utf-8")
    commands = {
        "S0": ["git status --short", "git log -3 --oneline"],
        "S1": [f"python scripts/v5/diagnose_provider_network.py --out {out.relative_to(ROOT).as_posix()}/network-s1",
               f"python scripts/v5/provider_round02_probe.py --out {out.relative_to(ROOT).as_posix()}/s1-completion --base-url https://api.inferera.com/v1"],
        "S2": [f"python scripts/v5/benchmark_provider_round02.py --out {out.relative_to(ROOT).as_posix()} --phase prepare"],
        "S3": [f"python scripts/v5/benchmark_provider_round02.py --out {out.relative_to(ROOT).as_posix()} --phase protocol",
               f"python scripts/v5/benchmark_provider_round02.py --out {out.relative_to(ROOT).as_posix()} --phase protocol-followup"],
        "S4": [f"python scripts/v5/compare_round02_efforts.py --out {out.relative_to(ROOT).as_posix()} --phase reliability",
               f"python scripts/v5/compare_round02_efforts.py --out {out.relative_to(ROOT).as_posix()} --phase quality"],
        "S5": [f"python -B scripts/v5/verify_round02_resume.py --out {out.relative_to(ROOT).as_posix()}",
               f"python -B -m pytest -p no:cacheprovider tests/v5 tests/m1 -q --junitxml={out.relative_to(ROOT).as_posix()}/PROVIDER_REGRESSION_R3.xml"],
        "S6": [f"python -B scripts/v5/finalize_round02_resume.py --out {out.relative_to(ROOT).as_posix()}"]}
    atomic_json(out / "COMMANDS.json", {"executed": commands,
        "warning": "Do not remove STOP or rerun paid phases; new external authorization and fresh task/run identities required after provider resolution."})
    statuses = [("S0", "PASS", "BASELINE.json", "39358 historical files preserved; writer released"),
        ("S1", "PARTIAL", "NETWORK_PATH_DIAGNOSIS.json", "Initial complete success; auth401 recurred during Q; all paid work stopped"),
        ("S2", "PARTIAL", "ALL_CANDIDATE_DISPOSITIONS.csv", "20 live schemas/catalog IDs; Grok output limit unresolved, no invented value"),
        ("S3", "PARTIAL", "REQUEST_RESULTS.csv", "19 models called,18 full protocol pass; MiniMax strict output failures; no current healthy authorization"),
        ("S4", "BLOCKED", "SCORECARD_ALL_MODELS.csv", "R complete two short batches; Q4 started/536 planned,0 valid pairs; B and rankings unavailable"),
        ("S5", "PARTIAL", "REPLAY_RESUME.json", "Mock and actual zero-send resume PASS; real healthy fallback NOT_RUN_AUTH_STOP"),
        ("S6", "PARTIAL", "ROUND_REPORT.md", "Auditable blocked handoff; no quality-qualified active profile or model selection")]
    atomic_json(out / "STAGES.json", [{"stage": s, "status": status, "commands": commands[s], "exit_code": 0,
        "source_hash": runtime if s in {"S5", "S6"} else read(out / "BASELINE.json")["runtime_sha256"] if s == "S0" else "UNKNOWN_EXACT_STAGE_TREE_SEE_ROUTING_VERSION_PROVENANCE",
        "settlement_source_hash": runtime, "evidence_paths": [evidence], "counts": totals["denominators"] if s == "S4" else {},
        "limitations": limitation, "exit_code_note": "Script exit0 is evidence persistence, not scientific or stage PASS"}
        for s, status, evidence, limitation in statuses])
    model_rows = []
    for model in dict.fromkeys(c["model"] for c in plan["configs"]):
        subset = [r for r in scores if r["exact_api_id"] == model]
        n, good = sum(r["R_planned"] for r in subset), sum(r["R_pass"] for r in subset)
        model_rows.append({"model": model, "protocol": subset[0]["protocol"], "planned": n, "PASS": good,
            "FAIL": sum(r["R_fail"] for r in subset), "NOT_RUN": sum(r["R_NOT_RUN"] for r in subset),
            "Wilson95_completed": wilson(good, sum(r["R_pass"]+r["R_fail"] for r in subset)),
            "two_batch_all_pass_modes": [r["config_id"].split("--")[1] for r in subset if r["R_pass"] == 8]})
    csv_write(out / "MODEL_LEVEL_R_STATISTICS.csv", model_rows)
    mode_table = "\n".join(f"|{r['model']}|{r['protocol']}|{', '.join(r['two_batch_all_pass_modes'])}|{r['PASS']}/{r['planned']}|" for r in model_rows)
    (out / "COMPATIBILITY_AND_EFFORT_REPORT.md").write_text(f"""# 协议、档位与效果

以下为鉴权再次失败前的短窗口两批实测，非当前授权保证。每档4任务×2批；每个工具任务有真实tool call→工具结果→final。R1 03:04:57–03:13:27 UTC，R2 03:13:27–03:22:39 UTC，不重叠但连续，不能说明跨日/长期稳定。67配置中65两批完整PASS，2为PROVISIONAL。R计划536：533PASS、2FAIL、1NOT_RUN；执行分母535。Wilson按实际完成n计算，计划分母和NOT_RUN同时列出，不将这些相关检查视为独立长期试验。

|精确ID|协议|两批全通过档位/模式|R通过/计划|
|---|---|---|---|
{mode_table}

Astra low：R1多轮明确HTTP503失败，工具NOT_RUN；R2通过。Kimi low：R2未给单个工具调用，属于输出质量失败，HTTP请求本身成功。MiniMax Chat与Messages正文夹think标签，严格收据失败，未剥离文字伪称成功。Meta原Chat本地工具预检漏目录上限已修复；新Responses全循环通过，原失败保留。Grok缺可核实数值输出上限，BLOCKED_DOCUMENTATION，POST=NOT_RUN。

Q统一题库536计划，仅4任务启动：Claude xhigh第一题HTTP200明确provider policy refusal，第二题HTTP401；Luna none第一题非JSON；Qwen Max medium第一阶段成功后受全局STOP中断。Q有532未启动，另1中断，不能把中断归为Qwen能力失败。工程合法非重复pair=0，任何模型的单位工程pair/机器合格成本NOT_COMPUTABLE。昂贵旗舰对高性价比的同题增益、档位质量收益和角色排名NOT_ESTABLISHED；不得用R收据效率代替Q产出。

原始attempt保留原类别；REQUEST_RESULTS.csv将明确refusal另标PROVIDER_POLICY_REFUSAL，不混为网络。JSON语法和现行期望对象验证、工具循环、质量结果分别列出。各档输入/输出/推理token、finish_reason、精确参数、usage、延迟及证据SHA见该表和scorecard。未返回推理拆分记UNKNOWN，非0；未做stream TTFT、极限输出/中长输入B、真实健康备援，均NOT_RUN_AUTH_STOP。当前auth再次阻塞，没有通过盲目重试制造恢复。
""", encoding="utf-8")
    (out / "NEXT_ACTIONS.md").write_text("""# 最少下一步

1. 账户负责人联系AIHubMix：提供2026-10-20 11:27:28.947北京时间、api.inferera.com/v1/messages、claude-opus-5-5、HTTP401、请求SHA 781031dd56f996a1117c067fb2f9c85da3bf6f70ae99718dd94ac21b74d060b1；确认Key/账户/渠道权限及合规安全研究任务的服务范围。此前同地址成功，且前一任务有明确policy refusal；关联原因仅是假设，需服务方确认。无需发送Key到聊天，也不要全局修改代理。
2. 获服务方明确恢复后，用户授权独立新run和全新微型请求验证；保留本轮STOP及全部终态，不直接清STOP续发。再完成固定Q、必要B和安全健康备援，才可启用本轮加载接口选择生成路线。已有4条历史未知请求仅查询服务端状态/账单，不盲重发。
3. Gold两位真实独立盲审与PI裁决仍由负责人完成（Round01交付材料）；其后才可按既定固定controls重新资格审阅候选并恢复FIRST_MACHINE_QUALIFIED。不得通过更换审阅模型刷PASS。正式生产、Pilot、Campaign、冻结本轮均未执行。
""", encoding="utf-8")
    (out / "REPLAY_RESUME.md").write_text("""# 恢复与不重发

REPLAY_RESUME.json由禁止任何generate调用的NoNetwork端口实测：155个已结束协议结果、4个Q结果复读，原始请求/响应逐字节不变；全部原始路由事件哈希链验证，旧4未知请求SHA无交集，401后没有新REQUEST_STARTED。已在途任务仅保存返回，不发后续阶段。

新路由loader用真实空profile实测拒绝启用：没有完整Q和工程pair，GENERATOR不得激活。正例/篡改/跨族/越权等用Mock测试，不能当作真实资格。原两个独审draw各18/18门槛保留；审阅与生成角色隔离，DeepSeek1017排除工厂角色，正式SUT不切换。

重跑安全只读验证：python -B scripts/v5/verify_round02_resume.py --out artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z。不要重跑收费阶段或可靠性main；后者会写时段标记。新任务必须在外部权限解决后采用新run_id，已有证据不覆盖。
""", encoding="utf-8")
    summary = {"status": "BLOCKED_AUTH_PERMISSION_RECURRED", "HEAD": head, "runtime_sha256": runtime,
        "PROVIDER_RECOVERED": "NO_AT_END_INITIAL_YES", "CATALOG_VERIFIED": 20, "models_called": 19,
        "models_full_protocol_pass": 18, "CONFIG_VERIFIED": 67, "STABLE_OBSERVED_SHORT_WINDOW_BEFORE_401": 65,
        "PROVISIONAL": 2, "active_healthy_profiles": 0, "regression": regression, "writer": "RELEASED",
        "FIRST_MACHINE_QUALIFIED": "BLOCKED", "Gold_PI": "HUMAN_REQUIRED", "auditors_qualified": 0,
        "scientific_acceptance": "NOT_ESTABLISHED", "formal_accepted": False, "publication_ready": False,
        "formal_production_Pilot_Campaign_freeze": "NOT_RUN", "totals": totals}
    atomic_json(out / "SUMMARY.json", summary)
    (out / "ROUND_REPORT.md").write_text(f"""# Round02 续跑交接

## 摘要（事实）

工作区D:\\Project\\ioa_codex_spec，HEAD `{head}`，runtime `{runtime}`，writer已释放；39358历史文件未变。PROVIDER_RECOVERED=NO（开始新MiMo Pro HTTP200、served精确匹配、usage120，质量阶段再次HTTP401）。目录20，实际调用19款、18款协议全通过；配置67，65短窗口双批全过、2暂定；当前健康配置0。所有角色选型NOT_ESTABLISHED，独审未资格。FIRST_MACHINE_QUALIFIED=BLOCKED，Gold/PI=HUMAN_REQUIRED。

## 阶段与命令

STAGES.json逐S0–S6列真实命令、exit_code、runtime、证据、分母与限制；exit0只证明脚本结束和保存结果。S0 PASS；S1/S2/S3 PARTIAL；S4 BLOCKED；S5/S6 PARTIAL。先S1有效completion，再目录、协议、分档R/Q；新增401立即停收费。命令细节见COMMANDS.json；不要直接重跑收费阶段。

## 核心表与统计

REQUEST_RESULTS.csv给每个attempt的精确ID/servedID、协议/endpoint、参数、输出预算、推理/输出/输入token、单价来源、费用、延迟、HTTP、finish、JSON/工具/质量状态和SHA。SCORECARD_ALL_MODELS.csv为67配置计划分母；ALL_CANDIDATE_DISPOSITIONS.csv覆盖未入矩阵的Grok/MiniMax；MODEL_LEVEL_R_STATISTICS.csv给模型级Wilson与完成/未执行数。完整协议/档位见COMPATIBILITY_AND_EFFORT_REPORT.md。两批相邻约18分钟，不是长期稳定保证。

新completion attempts={totals['attempts']}，成功持久响应{totals['statuses'].get('SUCCEEDED', 0)}，路由失败5，无新UNKNOWN；HTTP200不等于工具/质量PASS。R计划536，533通过、2失败、1未执行；Q计划536，4启动、0有效pair、532未启动，其中Qwen为停止中断。费用已知小计USD {totals['cost']['known_subtotal_usd']:.9f}，{totals['cost']['missing_usage_or_rate_attempts']}条usage/价格缺失，总额UNKNOWN，实际账单UNKNOWN。202479仅已返回总token小计，未返回token不记0。无工程pair，无独审，两个单位成本均NOT_COMPUTABLE。AA指标仅先验，未混入网关账单。

## 失败、纠正与证据边界

- 原401、Round01无HTTP/curl28与本轮先成功后401分别列NETWORK_PATH_DIAGNOSIS.md/.json；本次401需服务方解释Key/账户/渠道权限。前一Claude政策拒绝与401的关联未经证实，未改写提示规避拒绝。
- HTTP200头+curl28残缺JSON的最小负例在PARTIAL_HTTP_REPRODUCTION.xml原始FAIL；适配器现在显式REQUEST_UNRESOLVED，路由禁止重发/切模型，PARTIAL_HTTP_REGRESSION.xml与最终回归PASS。未知终态是本地Mock复现，本轮在线新UNKNOWN=0，旧4保留。
- Meta工具上限本地预检漏catalog已修复；原失败保留，修复后的定向XML及新Responses协议证据PASS。MiniMax夹think文本、Astra明确503、Kimi未调用工具、Luna非JSON、Claude明确拒绝和401均保留，未刷结果。
- STUDY_GUARD_TESTS.xml、R3.xml保留初始夹具失败；R2/R4及最终回归通过。首次smart-search命令从Python直接启动遇WinError2，后改用PowerShell已有CLI，官方材料抓取成功；未将工具失败伪称Provider失败。
- 首版ZIP通过CRC/成员SHA，但独立提取runtime校验FAIL：仅打包tracked源码漏掉现行权威哈希会计入的6个ignored egg-info文件。PACKAGE_RUNTIME_FAILURE.json保存差异与旧ZIP哈希；新版纳入全部src/contracts/config非缓存文件，不修改权威哈希算法或历史结果。

## 源码交付与权限

复用ModelPort/AIHubMixAdapter/AuxiliaryRouter；新增协议/分档/汇总/只读核验脚本，routing1.3.1修复残缺HTTP未知终态。数据工厂增加可选工程profile读取，绑定源码/证据/参数且只授GENERATOR权限；无完整Q时真实profile为空并拒绝启动，Mock正负例覆盖，真实健康备援NOT_RUN。固定Gold、Oracle、18构念、评分器、正式被测模型及原有历史不变，无新Goal/v6，无push。

完整源码文件SHA见SOURCE_MANIFEST.json；最终tests/v5+tests/m1 `{regression['tests']}`通过，0failure/error/skip（PROVIDER_REGRESSION_R3.xml）；定向故障138通过是子集，不能累加。原始测试FAIL历史保留。REPLAY_RESUME.json证明0新调用恢复、字节不变与401后0新请求；PROTECTED_HISTORY.json证明旧39358文件不变。在线S1/P/R事件绑定routing1.3.0，Q绑定1.3.1及完整runtime；P/R当时完整源码树未独立快照，阶段该项UNKNOWN，不能把最终源码回归冒称在线重测；逐请求版本见ROUTING_VERSION_PROVENANCE.json。

## 剩余阻塞与下一轮

PARETO_AND_ROLE_RECOMMENDATIONS.md明确全角色NOT_ESTABLISHED，AUXILIARY_ROUTING_PROFILE.json版本化但无活动contracts。未完成公平质量、档位收益、单位工程成本与长输入B/真实健康备援；不能将协议成本当产出成本。最少用户操作（≤3）见NEXT_ACTIONS.md。FIRST_MACHINE_QUALIFIED仍需外部鉴权稳定、完整质量选型及Gold双盲审/PI裁决后按既定controls资格流程再启用；现在不建议恢复正式闭环。
""", encoding="utf-8")
    artifacts = {p.relative_to(out).as_posix(): sha(p) for p in out.rglob("*") if p.is_file()
                 and p.name != "EVIDENCE_INDEX.json" and not p.name.endswith(".lock")}
    atomic_json(out / "EVIDENCE_INDEX.json", {"version": "round02-resume-handoff/1", "summary": summary,
        "files": artifacts, "self_excluded": "EVIDENCE_INDEX.json", "old_evidence_retained_on_host": True})
    return summary


def package(out, destination):
    import package_chatgpt_review as review
    summary = read(out / "SUMMARY.json")
    assert summary["runtime_sha256"] == source_tree_hash(ROOT)
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines())
    prefix = out.relative_to(ROOT).as_posix() + "/"
    review.selected = lambda p: p.parts[0] in {"src", "contracts", "config"} or p.as_posix() in tracked or p.as_posix().startswith(prefix)
    review.EVIDENCE = {prefix + "ROUND_REPORT.md", prefix + "EVIDENCE_INDEX.json"}
    return review.main(destination, out / "ROUND_REPORT.md", snapshot_metadata={"kind": "Round02_auth_recurred_blocked_handoff",
        "source_git_head": summary["HEAD"], "runtime_source_sha256": summary["runtime_sha256"],
        "provider_calls_during_packaging": 0, "provider_calls_in_retained_study": summary["totals"]["attempts"],
        "formal_accepted": False, "limitations": "All current Round02 evidence and tracked source included. Prior experiment corpora/archives remain on host, bound by protection hashes. User untracked directories and credentials excluded. No quality-based model selection or scientific acceptance."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    args = parser.parse_args()
    if args.package:
        print(json.dumps(package(args.out.resolve(), args.package), ensure_ascii=False))
    else:
        print(json.dumps(finalize(args.out.resolve()), ensure_ascii=False))
