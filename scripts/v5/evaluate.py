"""Run/report/replay supplied v5 cases. This entry never generates or freezes research data."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.v5.evaluation import atomic_json, publish_report, read_cases, read_results, run_batch, safe_id, writer_lock
from ioabench.v5.replay import replay_case
from ioabench.v5.reporting import build_report


async def _preflight(adapter):
    profile = await adapter.resolve("deepseek-v4.1-flash")
    request = ModelRequest(
        ({"role": "user", "content": "Reply READY."},), {"max_tokens": 512},
        role_metadata={"role": "ENGINEERING_IDENTITY_PROBE"})
    response = await adapter.generate(profile, request)
    metadata = response.provider_metadata
    identity = {"body_model": str(metadata.get("model", "")),
                "gateway_model": str(metadata.get("transport_metadata", {}).get("x-aihubmix-model", ""))}
    identity["body_aliases"] = sorted({identity["body_model"], profile.model_id})
    return profile, identity, {"request": asdict(request), "response": asdict(response), "identity": identity,
                              "verified": bool(identity["body_model"]) and identity["gateway_model"] == "deepseek-v4.1-flash",
                              "purpose": "ENGINEERING_IDENTITY_PROBE; not task-performance evidence"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--cases", type=Path, required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--suite", nargs="+", default=["all"])
    run.add_argument("--mode", choices=["reference", "smoke"], default="reference")
    run.add_argument("--reference-policy", choices=["witness", "naive", "recovery"], default="witness")
    run.add_argument("--resume", action="store_true")
    for name in ("report", "replay"):
        sub = commands.add_parser(name)
        sub.add_argument("--run-id", required=True)
        if name == "replay":
            sub.add_argument("--case-id")
    args = parser.parse_args()
    safe_id(args.run_id)
    directory = ROOT / "artifacts" / "v5" / "evaluations" / args.run_id
    if args.command == "run":
        suites = None if args.suite == ["all"] else args.suite
        read_cases(args.cases, suites)
        if args.mode == "reference":
            report = run_batch(ROOT, args.cases, run_id=args.run_id,
                               profile=ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
                               reference_policy=args.reference_policy, suites=suites, resume=args.resume)
        else:
            load_workspace_env(ROOT / ".env")
            adapter = AIHubMixAdapter(request_timeout=900)
            if args.resume:
                pin = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                profile, identity = ModelProfile(**pin["profile"]), pin["expected_identity"]
            else:
                if (directory / "manifest.json").exists():
                    raise FileExistsError("run exists; use --resume")
                profile, identity, probe = asyncio.run(_preflight(adapter))
                atomic_json(directory / "identity-probe.json", probe)
                if not probe["verified"]:
                    raise ValueError("preflight identity unverified; evidence retained in identity-probe.json")
            report = run_batch(ROOT, args.cases, run_id=args.run_id, profile=profile, port=adapter,
                               parameters={"temperature": 0.0, "max_tokens": 131072}, suites=suites,
                               expected_identity=identity, resume=args.resume)
        checkpoint = json.loads((directory / "checkpoint.json").read_text(encoding="utf-8"))
        print(json.dumps({"report": checkpoint["report"], "evidence_classes": report["evidence_classes"],
                          "status": checkpoint["status"]}, ensure_ascii=False))
    elif args.command == "report":
        with writer_lock(directory):
            rows = read_results(directory)
            paths = publish_report(build_report(rows, json.loads((directory / "manifest.json").read_text(encoding="utf-8"))), directory)
        print(paths["html"])
    else:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        ids = [args.case_id] if args.case_id else [case["case_id"] for case in manifest["cases"]]
        results = []
        for case_id in ids:
            try:
                results.append(replay_case(ROOT, args.run_id, case_id))
            except Exception as exc:
                results.append({"case_id": case_id, "passed": False, "error": f"{type(exc).__name__}: {exc}"})
        print(json.dumps({"passed": all(item["passed"] for item in results), "cases": results}, ensure_ascii=False))
        return 0 if all(item["passed"] for item in results) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
