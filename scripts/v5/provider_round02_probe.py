"""One fresh S1 completion through ModelPort; cached/unknown requests are never resent."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env
from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryContract, AuxiliaryRouter, redact
from ioabench.v5.ai_generation.model_routing import auxiliary_parameters
from ioabench.v5.evaluation import atomic_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


async def run(out, base_url):
    if (out / "S1_RESULT.json").exists():
        print(json.dumps({"resume": "NO_SEND", **read(out / "S1_RESULT.json")}))
        return
    out.mkdir(parents=True, exist_ok=True)
    load_workspace_env(ROOT / ".env")
    port = AIHubMixAdapter(base_url=base_url, stop_on_provider_error=True, request_timeout=60)
    transport = port._requester
    sequence = len(list(out.glob("http-*.json")))

    def recording_requester(method, path, body):
        nonlocal sequence
        sequence += 1
        record = {"method": method, "endpoint": base_url, "path": path,
                  "at_utc": datetime.now(timezone.utc).isoformat(), "request_body": body,
                  "request_body_sha256": canonical_sha256(body)}
        started = time.monotonic()
        try:
            payload = transport(method, path, body)
            record["decoded_http_response"] = payload
            return payload
        except Exception as exc:
            record.update(error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            record["elapsed_ms"] = (time.monotonic() - started) * 1000
            atomic_json(out / f"http-{sequence:03d}.json", redact(record))

    port._requester = recording_requester
    plan_path = out / "PREREGISTRATION.json"
    if plan_path.exists():
        plan = read(plan_path)
        if plan["base_url"] != base_url:
            raise ValueError("cannot reroute an existing S1 task")
        catalog, schema = read(out / "CATALOG.json"), read(out / "SCHEMA.json")
    else:
        catalog = list(await port.discover_models())
        schema = await port.describe_model("mimo-v2.6-pro")
        parameters = auxiliary_parameters(schema, output_budget=2048)
        receipt = "round02-" + uuid.uuid4().hex
        prompt = 'Return exactly this JSON object, with no extra text: ' + json.dumps({"receipt": receipt, "ok": True})
        plan = {"at_utc": datetime.now(timezone.utc).isoformat(), "base_url": base_url,
                "model_id": "mimo-v2.6-pro", "request_id": receipt, "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "parameters": parameters,
                "max_completion_sends": 1, "historical_unresolved_resends": 0,
                "unknown_or_auth": "STOP_NO_RETRY_NO_FAILOVER", "scope": "S1_PROTOCOL_ONLY_NOT_ROLE_QUALIFICATION"}
        atomic_json(out / "CATALOG.json", catalog)
        atomic_json(out / "SCHEMA.json", schema)
        atomic_json(plan_path, plan)
    entry = next(row for row in catalog if (row.get("model_id") or row.get("id")) == plan["model_id"])
    contract = AuxiliaryContract(ModelProfile("aihubmix", plan["model_id"], {}, {}), plan["parameters"], entry,
                                 str(plan_path), ("AUX_PROTOCOL_PROBE",))
    router = AuxiliaryRouter(port, [contract], catalog, out / "model_io", max_attempts_per_model=1)
    result = {"status": "BLOCKED", "provider_recovered": "UNVERIFIED", "base_url": base_url,
              "preregistration_sha256": canonical_sha256(plan), "request_id": plan["request_id"]}

    def validate(response):
        if json.loads(response.text) != {"receipt": plan["request_id"], "ok": True}:
            raise ValueError("MODEL_QUALITY: receipt not preserved")
        if (response.provider_metadata.get("transport_metadata") or {}).get("http_status") != 200:
            raise ValueError("unverified HTTP response")
        if not response.usage:
            raise ValueError("missing usage")

    try:
        response = await router.invoke("AUX_PROTOCOL_PROBE", plan["request_id"],
                                       ModelRequest(messages=({"role": "user", "content": plan["prompt"]},), parameters={}),
                                       validate=validate)
        result.update(status="PASS", provider_recovered="YES", response=asdict(response))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=redact(str(exc)))
    atomic_json(out / "S1_RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", choices=("https://aihubmix.com/v1", "https://api.inferera.com/v1"), required=True)
    args = parser.parse_args()
    asyncio.run(run(args.out, args.base_url))


if __name__ == "__main__":
    main()
