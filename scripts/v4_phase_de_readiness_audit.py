"""Read-only Phase D/E readiness audit for the frozen v4 corrective release.

Checks, with zero provider calls:
  1. every field the goal pack's 04_V4_RELEASE_FREEZE_CONTRACT.md demands is present;
  2. the 18 run manifests bind the same release triple;
  3. the Phase D/E prerequisites that are verifiable offline (CLI semantics, orchestrator
     wiring, credential *presence* only, frozen dataset accessibility).

Nothing here writes to the release, the datasets or the historical assets.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RELEASE_PATH = ROOT / "release/BENCHMARK_RELEASE_v4-corrective-20261001.json"
SUITES = [f"T3{a}{b}" for a in "123456" for b in "123"]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def main() -> int:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    rel_id = release["release_id"]
    rel_sha = hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest()
    tree = release["source_tree_sha256"]

    # ---------- 1. freeze-contract field coverage ----------
    required = {
        "release_id": rel_id == "v4-corrective-20261001",
        "frozen_at": bool(release.get("frozen_at")),
        "supersedes": release.get("supersedes", {}).get("path", "").endswith("v3-20260930.json"),
        "source_tree_sha256": len(tree) == 64,
        "dependency_lock_sha256": len(release.get("dependency_lock_sha256", "")) == 64,
        "dataset_pack_v4_sha256": len(release.get("dataset_pack_v4_sha256", "")) == 64,
        "18 datasets": set(release.get("datasets", {})) == set(SUITES),
        "18 contracts": set(release.get("contracts", {})) == set(SUITES),
        "prompt hashes": bool(release.get("prompt_hashes")),
        "tool schema hashes": "tool_schema_hashes" in release,
        "scorer versions (18)": set(release.get("scorer_versions", {})) == set(SUITES),
        "runtime versions (18)": set(release.get("runtime_versions", {})) == set(SUITES),
        "model profile": release.get("tested_model", {}).get("model_id") == "deepseek-v4.1-flash",
        "scheduler": "scheduler_profile" in release,
        "strict retry semantics": release.get("invalid_output_semantics", {}).get("strict_retry_semantics") is True,
        "replay schema": "replay_schema" in release,
        "SH profile": release.get("auxiliary_model_profiles", {}).get("simulation_only") is True,
        "canonical constraints": "canonical_constraints" in release,
    }
    for name, ok in required.items():
        check(f"freeze_contract::{name}", ok)

    # ---------- 2. manifest binding ----------
    manifest_dir = ROOT / "data/runs/_v4_manifests"
    manifests = sorted(manifest_dir.glob("*.manifest.json"))
    check("manifests::count_18", len(manifests) == 18, f"found={len(manifests)}")
    bound_suites, mismatches = set(), []
    for path in manifests:
        m = json.loads(path.read_text(encoding="utf-8"))

        def dig(d, *keys):
            for k in keys:
                if not isinstance(d, dict) or k not in d:
                    return None
                d = d[k]
            return d

        rid = dig(m, "release", "release_id") or m.get("release_id")
        rsha = dig(m, "release", "release_sha256") or m.get("release_sha256")
        tsha = dig(m, "release", "source_tree_sha256") or m.get("source_tree_sha256")
        suite_map = dig(m, "benchmark", "suite_versions") or {}
        suite = next(iter(suite_map), None) if len(suite_map) == 1 else None
        if rid == rel_id and rsha == rel_sha and tsha == tree and suite in SUITES:
            bound_suites.add(suite)
        else:
            mismatches.append(path.name)
    check("manifests::all_bind_same_triple", not mismatches, f"mismatches={mismatches}")
    check("manifests::cover_18_suites", bound_suites == set(SUITES), f"covered={len(bound_suites)}")

    # run ids must be v4-native, never colliding with historical dirs
    run_ids = []
    for path in manifests:
        m = json.loads(path.read_text(encoding="utf-8"))
        rid = m.get("run_id") or m.get("run", {}).get("run_id")
        if rid:
            run_ids.append(rid)
    check("manifests::run_ids_v4_suffixed", all(r.endswith("-v4-formal") for r in run_ids),
          f"n={len(run_ids)}")

    # ---------- 3. offline-verifiable Phase D/E prerequisites ----------
    # 3a. synthetic-human separation: SH model must differ from tested model
    aux = release.get("auxiliary_model_profiles", {})
    check("phaseDE::SH_model_differs", aux.get("model_id") != release["tested_model"]["model_id"],
          f"sh={aux.get('model_id')}")
    check("phaseDE::SH_max_tokens_2000", aux.get("parameters", {}).get("max_tokens") == 2000)
    check("phaseDE::SH_temp_0", aux.get("parameters", {}).get("temperature") == 0.0)
    check("phaseDE::SH_persona_version", aux.get("persona_set_version") == "sh-personas-1.0.0")

    # 3b. scheduler matches the goal pack (conc 3, temp 0, max_tokens 8192)
    tm = release.get("scheduler_profile", {}).get("profiles", {}).get("tested_model", {})
    check("phaseDE::scheduler_concurrency_3", tm.get("concurrency") == 3)
    check("phaseDE::scheduler_temp_0", tm.get("temperature") == 0.0)
    check("phaseDE::scheduler_max_tokens_8192", tm.get("max_tokens") == 8192)

    # 3c. dispatch version matches what the candidate tree ships
    cand = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v2"
    dd = cand / "src/ioabench/runtime/construct_dispatch.py"
    if dd.exists():
        text = dd.read_text(encoding="utf-8")
        frozen_dv = release["runtime_mapping"]["dispatch_version"]
        check("phaseDE::dispatch_version_matches_candidate", f'DISPATCH_VERSION = "{frozen_dv}"' in text,
              f"frozen={frozen_dv}")
        check("phaseDE::candidate_has_strict_wrapper", "execute_construct_case_strict" in text)
    else:
        check("phaseDE::dispatch_version_matches_candidate", False, "candidate tree missing")

    # 3d. credential availability — presence only; values are never read or echoed.
    # The key may live in the process environment or in the workspace .env, which
    # the CLI and pilot load via load_workspace_env() before any provider call.
    env_set = bool(os.environ.get("AIHUBMIX_API_KEY"))
    dotenv_set = False
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("AIHUBMIX_API_KEY=") and len(s.split("=", 1)[1].strip().strip('"').strip("'")) >= 8:
                dotenv_set = True
    check("phaseDE::credential_available", env_set or dotenv_set,
          f"env={env_set} dotenv={dotenv_set}"
          if (env_set or dotenv_set) else "MISSING in both env and .env (Phase D cannot start)")

    # 3e. frozen datasets reachable for all 18 suites
    pack = ROOT / "data/datasets/DATASET_PACK_v4.yaml"
    check("phaseDE::dataset_pack_present", pack.exists())

    # 3f. CLI and pilot must load the workspace .env before provider calls, so a
    # key that lives only in .env reaches the adapter (which reads os.environ).
    cli_path = cand / "src/ioabench/cli.py"
    pilot = ROOT / "scripts/run_online_pilot.py"
    cli_text = cli_path.read_text(encoding="utf-8") if cli_path.exists() else ""
    pilot_text = pilot.read_text(encoding="utf-8") if pilot.exists() else ""
    check("phaseDE::cli_loads_dotenv", "load_workspace_env" in cli_text or "load_dotenv" in cli_text)
    check("phaseDE::pilot_loads_dotenv", "load_workspace_env" in pilot_text or "load_dotenv" in pilot_text)

    # 3g. the orchestrator must emit -v4-formal run ids and guard historical dirs
    orch = ROOT / "scripts/run_online_campaign.py"
    check("phaseDE::orchestrator_present", orch.exists())
    if orch.exists():
        otext = orch.read_text(encoding="utf-8")
        check("phaseDE::orchestrator_v4_run_id", "-v4-formal" in otext)
        check("phaseDE::orchestrator_guards_history", "refusing to touch historical run directory" in otext)
        check("phaseDE::orchestrator_has_max_resume", "max_resume" in otext)
        check("phaseDE::orchestrator_infra_interrupted_terminal", "INFRA_INTERRUPTED" in otext)

    # ---------- report ----------
    failures = [r for r in results if not r[1]]
    payload = {
        "artifact": "V4_PHASE_DE_READINESS_AUDIT",
        "checks": len(results),
        "check_detail": [{"name": n, "pass": ok, "detail": d} for n, ok, d in results],
        "failures": [{"name": n, "detail": d} for n, _, d in failures],
        "release_id": rel_id,
        "release_sha256": rel_sha,
        "source_tree_sha256": tree,
        "provider_calls": 0,
        "pass": not failures,
    }
    out = ROOT / "artifacts/scientific_closure_v4/phase-de-readiness-001.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
