"""Bounded exploratory run against the user's direct DeepSeek API key.

This never changes the formal AIHubMix/deepseek-v4.1-flash roster or freezes data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.models import DeepSeekAdapter  # noqa: E402
from ioabench.v5.evaluation import atomic_json, read_cases, run_batch, safe_id  # noqa: E402
from ioabench.v5.scenario_profiles import validate_profile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-tokens", type=int, default=131072)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 393216:
        parser.error("--max-tokens must be 1..393216 for the direct DeepSeek API")
    safe_id(args.run_id)
    directory = ROOT / "artifacts" / "v5" / "evaluations" / args.run_id
    if directory.exists():
        raise SystemExit("run directory already exists; use a new run ID to preserve evidence")
    for case in read_cases(args.cases):
        validate_profile(case)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("DEEPSEEK_API_KEY is required; it is never read from project files")
    adapter = DeepSeekAdapter(request_timeout=900)
    profile = asyncio.run(adapter.resolve("deepseek-flash"))
    catalog = asyncio.run(adapter.discover_models())
    if profile.model_id != "deepseek-flash" or not any(item.get("id") == profile.model_id for item in catalog):
        raise SystemExit("exact deepseek-flash identity was not confirmed by the live catalog")
    # Direct DeepSeek has no AIHubMix gateway header; the exact body model is authoritative here.
    identity = {"body_model": "deepseek-flash", "gateway_model": "",
                "endpoint_family": "openai-chat-completions", "base_url": adapter.base_url,
                "body_aliases": ["deepseek-flash"]}
    atomic_json(directory / "identity-probe.json", {
        "status": "LIVE_EXPLORATORY_IDENTITY_CONFIRMED", "requested_model_id": "deepseek-flash",
        "resolved_model_id": profile.model_id, "provider": profile.provider,
        "catalog_ids": sorted(str(item.get("id")) for item in catalog if item.get("id")),
        "expected_identity": identity, "formal_model_unchanged": "deepseek-v4.1-flash",
        "catalog_requests_before_batch": 2, "completion_requests_before_batch": 0,
    })
    report = run_batch(ROOT, args.cases, run_id=args.run_id, profile=profile, port=adapter,
                       parameters={"thinking": {"type": "enabled"}, "reasoning_effort": "high",
                                   "stream": False, "max_tokens": args.max_tokens},
                       expected_identity=identity, required_model_id="deepseek-flash")
    print(json.dumps({"run_id": args.run_id, "model_id": profile.model_id,
                      "evidence_class": "ENGINEERING_SMOKE_EXPLORATORY",
                      "scheduled": report.get("scheduled_cases"),
                      "observed": report.get("observed_cases"),
                      "report": str((directory / "checkpoint.json").resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
