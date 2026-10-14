"""v1.1.2/131072 pair recheck for T352 and T332 (PI-V5-006a closure, SMOKE_DIAGNOSTIC evidence).

The 12 T352/T332 smoke cases ran under the old v1.1.0/8192 budget, so the unified v1.1.2/131072
protocol had no T352/T332 coverage. This recheck runs ONE representative CONTROL/RISK pair per
suite under v1.1.2 and inspects each pair immediately: served identity, tool interaction,
execution status, truncation, exposure and evidence-record integrity. Systemic problems stop the
recheck; isolated model behavior does not. Not part of any benchmark protocol.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models import AIHubMixAdapter  # noqa: E402
from ioabench.v5.runner import append_result, run_case  # noqa: E402
import importlib.util

_spec = importlib.util.spec_from_file_location("pilot", ROOT / "scripts" / "v5" / "pilot.py")
pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pilot)

# Representative pairs: T352-F25-P1 (M stratum; its CONTROL was the 8192-truncation case, so this
# directly revalidates the previously problematic path) and T332-F15-P1 (M stratum, partner-register
# exception path).
PAIRS = {"T352": ("T352-F25-P1-CONTROL", "T352-F25-P1-RISK"),
         "T332": ("T332-F15-P1-CONTROL", "T332-F15-P1-RISK")}
RUN_ID = "v5-smoke-v112-pair-recheck"
EXPECTED_SERVED = "deepseek-v4-1-flash-260910"


def inspect_pair(rows: list[dict]) -> bool:
    ok = True
    for r in rows:
        recs = r["trace"]["records"]
        usage = [rec["response"].get("usage", {}) for rec in recs]
        served = {rec["response"].get("provider_metadata", {}).get("model") for rec in recs}
        truncations = [(i, u.get("completion_tokens"), rec["response"].get("finish_reason"))
                       for i, (u, rec) in enumerate(zip(usage, recs)) if rec["response"].get("finish_reason") == "length"]
        leaks = "observation firewall" in str(r.get("error")) or r["status"] == "LEAKAGE_BLOCKED"
        pair_ok = (served == {EXPECTED_SERVED} and r["status"] in ("COMPLETED", "INVALID_MODEL_OUTPUT")
                   and not leaks and r["exposure"]["exposed"] and r["exposure"]["opportunity"]
                   and all(rec["response"].get("elapsed_seconds") is not None for rec in recs))
        ok = ok and pair_ok
        print(f"  {r['case_id']} [{r['arm']}] status={r['status']} {r['outcome']['legacy_class']} "
              f"identity_ok={served == {EXPECTED_SERVED}} calls={len(recs)} "
              f"reasoning_chars={sum(len(rec['response'].get('reasoning_content') or '') for rec in recs)} "
              f"slowest={max((rec['response'].get('elapsed_seconds') or 0) for rec in recs):.1f}s "
              f"truncations={truncations} leakage={leaks} exposure={r['exposure']['exposed']}/{r['exposure']['opportunity']} "
              f"--> {'OK' if pair_ok else 'CHECK'}", flush=True)
    return ok


async def main() -> None:
    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve("deepseek-v4.1-flash")
    out = ROOT / "artifacts" / "v5" / "probes" / "v112-pair-recheck.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] != "RETRYABLE_INFRA_FAILURE":
                done.add(row["case_id"])
    for suite in ("T352", "T332"):
        version = pilot.resolve_dataset_version(suite, "5.1.5-candidate-20261006")
        wanted = set(PAIRS[suite])
        wanted_pair_ids = {case_id.rsplit("-", 1)[0] for case_id in wanted}
        pair_rows: list[dict] = []
        for control, risk in pilot.sample_pairs(suite, version, per_stratum=1):
            if control.pair_id not in wanted_pair_ids:
                continue
            for case in (control, risk):
                if case.case_id not in wanted or case.case_id in done:
                    continue
                result = await run_case(ROOT, case, adapter, profile, run_id=RUN_ID,
                                        parameters=pilot.PARAMETERS)
                result["evidence_class"] = "SMOKE_DIAGNOSTIC"
                result["dataset_version"] = version
                result["diagnostic"] = {"purpose": "v1.1.2/131072 pair recheck", "protocol_version": pilot.PROTOCOL_VERSION}
                append_result(out, result)
                pair_rows.append(result)
        print(f"== {suite} pair recheck under {pilot.PROTOCOL_VERSION} (max_tokens={pilot.PARAMETERS['max_tokens']})", flush=True)
        if not inspect_pair(pair_rows):
            print(f"  CHECK REQUIRED — stopping the recheck before any further batches", flush=True)
            return
    print("PAIR RECHECK COMPLETE: no systemic engineering issue observed", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
