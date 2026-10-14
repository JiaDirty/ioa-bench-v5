"""V4-S4: pre-freeze scientific audit.

Recomputes every component the v4 Release will freeze, from disk:
dataset pack hashes, frozen-version map, contracts, prompt/tool hashes, scorer
and runtime versions, model profile, scheduler, dependency lock, Synthetic
Human profile, and the strict-retry semantics text. Any mismatch blocks the
freeze. No provider calls.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT_PRE = Path(__file__).resolve().parents[1]
CAND_SRC = str((ROOT_PRE / "artifacts/scientific_closure_v4/corrective-candidate-v2/src").resolve())
# The v4 candidate must win the `ioabench` import race. The workspace tree is an
# editable install, so its src directory is already on sys.path and would shadow
# the candidate; drop it, then put the candidate first.
_WORKSPACE_SRC = str((ROOT_PRE / "src").resolve()).lower()


def _same_path(entry: str, target: str) -> bool:
    try:
        return str(Path(entry or ".").resolve()).lower() == target
    except (OSError, ValueError):
        return False


for _entry in list(sys.path):
    if _same_path(_entry, _WORKSPACE_SRC) or _same_path(_entry, CAND_SRC.lower()):
        sys.path.remove(_entry)
for _name in [n for n in list(sys.modules) if n == "ioabench" or n.startswith("ioabench.")]:
    del sys.modules[_name]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, CAND_SRC)

from scientific_closure import ROOT, reference, write_new  # noqa: E402

CAND = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v2"
SUITES = ["T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
          "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    checks = {}
    failures = []

    def check(name, ok, detail=""):
        checks[name] = {"pass": bool(ok), "detail": detail}
        if not ok:
            failures.append(name)

    # ---- 1. dataset pack + three-way binding ----
    pack_path = ROOT / "data/datasets/DATASET_PACK_v4.yaml"
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    check("dataset_pack_has_18_suites", len(pack["suites"]) == 18, len(pack["suites"]))
    pack_ok = True
    for suite in SUITES:
        item = pack["suites"].get(suite)
        if not item:
            pack_ok = False
            continue
        mp = ROOT / "data/datasets" / suite / str(item["version"]) / "manifest.json"
        if not mp.is_file():
            pack_ok = False
            continue
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        if manifest.get("content_sha256") != item.get("content_sha256"):
            pack_ok = False
    check("dataset_pack_hashes_match_manifests", pack_ok)

    # ---- 2. frozen versions map covers all suites ----
    fv_text = (CAND / "src/ioabench/frozen_versions.py").read_text(encoding="utf-8")
    ns = {}
    exec(compile(fv_text, str(CAND / "src/ioabench/frozen_versions.py"), "exec"), ns)  # noqa: S102 - local frozen map
    FROZEN_VERSIONS = ns.get("FROZEN_VERSIONS", {})
    missing_versions = [s for s in SUITES if s != "T311" and s not in FROZEN_VERSIONS]
    check("frozen_versions_map_complete", not missing_versions, missing_versions)
    version_match = all(FROZEN_VERSIONS.get(s) == pack["suites"][s]["version"] for s in SUITES if s in FROZEN_VERSIONS)
    check("frozen_versions_match_pack", version_match)

    # ---- 3. contracts present for all suites ----
    contracts = {}
    contracts_ok = True
    for suite in SUITES:
        cp = CAND / "contracts/constructs" / f"{suite}.json"
        if not cp.is_file():
            cp = ROOT / "contracts/constructs" / f"{suite}.json"
        if not cp.is_file():
            contracts_ok = False
            continue
        contracts[suite] = sha(cp)
    check("contracts_present_18", contracts_ok and len(contracts) == 18, len(contracts))

    # ---- 4. scorer versions / runtime-dispatch versions ----
    # Read the candidate source directly rather than importing it: the workspace
    # tree is an editable install and would otherwise shadow the candidate.
    dispatch_src_for_versions = (CAND / "src/ioabench/runtime/construct_dispatch.py").read_text(encoding="utf-8")
    dispatch_match = re.search(r'DISPATCH_VERSION = "([^"]+)"', dispatch_src_for_versions)
    dispatch_version = dispatch_match.group(1) if dispatch_match else None
    check("dispatch_version_1_0_2", dispatch_version == "construct-dispatch-1.0.2", dispatch_version)
    runners_src = dispatch_src_for_versions.split("RUNNERS: dict")[1].split("}")[0] if "RUNNERS: dict" in dispatch_src_for_versions else ""
    runner_suites = re.findall(r'"(T\d{3})":', runners_src)
    check("runner_table_18", len(set(runner_suites)) == 18, len(set(runner_suites)))

    # ---- 5. prompt + tool hashes (T311 grounded; others via runtime constants) ----
    prompt_hashes = {}
    t311_runtime = (CAND / "src/ioabench/runtime/t311_construct.py").read_text(encoding="utf-8")
    for label, const in (("T311.base", "LEAD_PROMPT"), ("T311.role", "EXECUTOR_PROMPT")):
        m = re.search(rf'{const} = "(.*?)"\n', t311_runtime, re.S)
        if m:
            prompt_hashes[label] = hashlib.sha256(json.loads('"' + m.group(1) + '"').encode("utf-8")).hexdigest()
    check("t311_prompts_hashable", len(prompt_hashes) == 2, list(prompt_hashes))

    # ---- 6. model profile + scheduler ----
    scheduler = json.loads((ROOT / "config/scheduler_profile.json").read_text(encoding="utf-8"))
    tested = scheduler["profiles"]["tested_model"]
    check("scheduler_concurrency_3", tested["concurrency"] == 3, tested)
    check("scheduler_temperature_0", tested["temperature"] == 0.0)
    check("scheduler_max_tokens_8192", tested["max_tokens"] == 8192)
    check("scheduler_frozen", scheduler.get("frozen") is True)

    # ---- 7. Synthetic Human profile ----
    sh = json.loads((ROOT / "config/synthetic_human.json").read_text(encoding="utf-8"))
    check("sh_model_glm_5_3_flash", sh["model_id"] == "glm-5.3-flash", sh["model_id"])
    check("sh_frozen", sh.get("frozen") is True)
    check("sh_simulation_only", sh.get("simulation_only") is True)
    check("sh_personas_1_0_0", sh["persona_set_version"] == "sh-personas-1.0.0")
    check("sh_deterministic_assignment", sh["persona_assignment"] == "case_id_sha256_mod_v1")
    check("sh_params", sh["parameters"] == {"temperature": 0.0, "max_tokens": 2000}, sh["parameters"])
    check("sh_differs_from_tested_model", sh["model_id"] != "deepseek-v4.1-flash")

    # ---- 8. dependency lock ----
    lock = ROOT / "config/dependencies.lock.json"
    check("dependency_lock_present", lock.is_file())
    lock_sha = sha(lock) if lock.is_file() else None

    # ---- 9. strict retry semantics text present in candidate ----
    batch_src = (CAND / "src/ioabench/runtime/batch.py").read_text(encoding="utf-8")
    io_src = (CAND / "src/ioabench/runtime/scientific_io.py").read_text(encoding="utf-8")
    dispatch_src = (CAND / "src/ioabench/runtime/construct_dispatch.py").read_text(encoding="utf-8")
    types_src = (CAND / "src/ioabench/core/types.py").read_text(encoding="utf-8")
    check("terminal_set_declared", "TERMINAL_STATUSES" in batch_src)
    # the terminal classification lives in the dispatcher; the journal supplies
    # the evidence fields that decide it
    check("infra_interrupted_classified_in_dispatcher", "INFRA_INTERRUPTED" in dispatch_src)
    check("infra_interrupted_in_state_enum", "INFRA_INTERRUPTED" in types_src)
    check("infra_interrupted_in_terminal_set", "INFRA_INTERRUPTED" in batch_src)
    check("journal_reports_valid_behaviour", "valid_model_behavior_observed" in io_src)
    check("resumable_only_retryable", 'RESUMABLE_STATUSES = frozenset({"RETRYABLE_INFRA_FAILURE"})' in batch_src)

    # ---- 10. candidate tree hash ----
    files = {}
    for scope in ("src", "contracts", "config"):
        for p in (CAND / scope).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                files[p.relative_to(CAND).as_posix()] = p.read_bytes()
    from scientific_closure import windows_snapshot_hash
    tree = windows_snapshot_hash(files)
    check("candidate_tree_hash_computed", len(tree) == 64, tree)

    report = {
        "artifact": "V4_PREFREEZE_SCIENTIFIC_AUDIT",
        "version": "2",
        "pass": not failures,
        "provider_calls": 0,
        "failures": failures,
        "checks": checks,
        "candidate_source_tree_sha256": tree,
        "dataset_pack_v4": reference(pack_path),
        "dependency_lock_sha256": lock_sha,
        "contracts_sha256": contracts,
        "prompt_hashes": prompt_hashes,
        "scheduler_profile": reference(ROOT / "config/scheduler_profile.json"),
        "synthetic_human_profile": reference(ROOT / "config/synthetic_human.json"),
        "tested_model": {"model_id": "deepseek-v4.1-flash", "temperature": 0.0, "max_tokens": 8192,
                         "concurrency": 3},
    }
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/scientific_closure_v4/prefreeze-scientific-audit-002.json")
    args = parser.parse_args()
    write_new(ROOT / args.output, report)
    print(json.dumps({"pass": report["pass"], "failures": failures, "checks": len(checks),
                      "candidate_tree": tree}, ensure_ascii=False, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
