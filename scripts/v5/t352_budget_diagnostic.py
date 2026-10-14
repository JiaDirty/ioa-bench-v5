"""T352 output-budget boundary diagnostic (PI-V5-006a exploratory, SMOKE evidence class).

The staged T352 smoke batch at the frozen protocol budget max_tokens=8192 produced 3/6
INVALID_MODEL_OUTPUT rows, all `finish_reason=length` with completion_tokens==8192 exactly, all on
mid-episode pure-thinking turns. This probe reruns exactly those sampled cases at max_tokens=16384
to test the boundary hypothesis (reasoning-length tail > 8192) before any versioned protocol
parameter change is proposed. Old attempt records are preserved; this writes to its own run id and
its own evidence file — never to the confirmation pilot or the smoke results.jsonl.
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

CASE_IDS = {"T352-F25-P1-CONTROL", "T352-F19-P2-RISK", "T352-F20-P1-RISK"}
MAX_TOKENS = 16384
RUN_ID = "v5-smoke-t352-mt16384"


async def main() -> None:
    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve("deepseek-v4.1-flash")
    version = pilot.resolve_dataset_version("T352", "5.1.5-candidate-20261006")
    out = ROOT / "artifacts" / "v5" / "probes" / "t352-mt16384-diagnostic.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] != "RETRYABLE_INFRA_FAILURE":
                done.add(row["case_id"])
    for control, risk in pilot.sample_pairs("T352", version, per_stratum=1):
        for case in (control, risk):
            if case.case_id not in CASE_IDS or case.case_id in done:
                continue
            result = await run_case(ROOT, case, adapter, profile, run_id=RUN_ID,
                                    parameters={"temperature": 0.0, "max_tokens": MAX_TOKENS})
            result["evidence_class"] = "SMOKE_DIAGNOSTIC"
            result["dataset_version"] = version
            result["diagnostic"] = {"purpose": "t352 output-budget boundary", "max_tokens": MAX_TOKENS}
            append_result(out, result)
            usage = [rec["response"].get("usage", {}) for rec in result["trace"]["records"]]
            print(case.case_id, result["status"],
                  "completion_max=", max((u.get("completion_tokens", 0) for u in usage), default=0),
                  "calls=", len(usage), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
