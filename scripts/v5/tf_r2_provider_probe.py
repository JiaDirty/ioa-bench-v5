"""R2 M3 live AIHubMix probe: parameter ceiling ladder + transport/identity +
JSON-content fidelity, all through the append-only R2 request ledger.

New request ids only; the sealed R1 STOP/ledger is never touched. Fidelity is
reported as three SEPARATE verdicts (04_模型调用: transport/identity validity is
not JSON-exactness, and JSON-exactness is not auth health).
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models.aihubmix import AIHubMixAdapter  # noqa: E402
from ioabench.v5.ai_generation import aihubmix_study  # noqa: E402
from ioabench.v5.ai_generation.factory import decode_json  # noqa: E402
from ioabench.v5.evaluation import atomic_json  # noqa: E402

CEILING_LADDER = (393216, 384000, 262144, 131072)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    load_workspace_env(ROOT / ".env")
    import os
    if not os.environ.get("AIHUBMIX_API_KEY"):
        raise ValueError("AIHUBMIX_API_KEY missing; no value logged")
    OUT.mkdir(parents=True, exist_ok=True)
    port = AIHubMixAdapter(stop_on_provider_error=True, request_timeout=900)
    catalog_path = OUT / "MODEL_CATALOG.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() \
        else list(await port.discover_models())
    atomic_json(catalog_path, catalog)
    study = aihubmix_study.AihubmixStudy(OUT, port, catalog)
    if study.stop.exists():
        raise ValueError("R2 study already stopped; inspect STOP.json")
    entry = study.catalog_entry
    contract: dict = {"version": "ioabench.v5.r2-provider-contract/1.0.0",
                      "captured_at_utc": utc(),
                      "provider": aihubmix_study.PROVIDER,
                      "base_url": aihubmix_study.BASE_URL,
                      "model_id": aihubmix_study.MODEL,
                      "endpoint_family": "openai.chat_completions",
                      "catalog_entry": {key: entry.get(key) for key in
                                        ("id", "model_id", "developer_id", "owned_by", "features")},
                      "budget_gate": "DISABLED (user-authorized; usage still recorded)",
                      "ceiling_ladder": [], "probes": []}

    # ---- ceiling ladder: tiny output, transport-level parameter validation ----
    accepted_ceiling = None
    for ceiling in CEILING_LADDER:
        request_id = f"r2-ceiling-{ceiling}-p1"
        params = aihubmix_study.parameters("high", max_tokens=ceiling)
        params["stream"] = False  # parameter probe, not generation
        try:
            probe = await study.invoke(OUT / "probes", request_id, [
                {"role": "user", "content":
                 'Return only JSON exactly like {"probe":"ceiling","ok":true}.'}], params)
            transport = probe.provider_metadata.get("transport_metadata") or {}
            row = {"max_tokens": ceiling, "outcome": "ACCEPTED",
                   "http_status": transport.get("http_status"),
                   "finish_reason": probe.finish_reason,
                   "usage": dict(probe.usage)}
            contract["ceiling_ladder"].append(row)
            accepted_ceiling = ceiling
            break
        except Exception as exc:
            message = str(exc)
            contract["ceiling_ladder"].append(
                {"max_tokens": ceiling, "outcome": "REJECTED",
                 "error_type": type(exc).__name__,
                 "detail": message[:300],
                 "classification": "PARAMETER_REJECTED" if "400" in message else "OTHER"})
            if "401" in message or "403" in message:
                contract["auth_status"] = "AUTH/PERMISSION FAILURE"
                atomic_json(OUT / "PROVIDER_CONTRACT.json", contract)
                print(json.dumps({"status": "AUTH_FAILED", "ceiling": None}, ensure_ascii=False))
                return 2
    contract["accepted_max_tokens_ceiling"] = accepted_ceiling
    if accepted_ceiling is None:
        atomic_json(OUT / "PROVIDER_CONTRACT.json", contract)
        print(json.dumps({"status": "NO_CEILING_ACCEPTED"}, ensure_ascii=False))
        return 1

    # ---- generation-path probe: frozen streaming protocol at the base profile --
    params = aihubmix_study.parameters("high",
                                       max_tokens=aihubmix_study.OUTPUT_PROFILE["base_max_tokens"])
    response = await study.invoke(OUT / "probes", "r2-json-fidelity-p1", [
        {"role": "user", "content":
         'Return only JSON exactly like {"receipt":"r2-json-fidelity-p1","ok":true} '
         'with those exact values.'}], params)
    transport = response.provider_metadata.get("transport_metadata") or {}
    try:
        payload = decode_json(response.text)
        json_shape_ok = isinstance(payload, dict)
        receipt_exact = payload.get("receipt") == "r2-json-fidelity-p1"
    except (TypeError, ValueError):
        payload, json_shape_ok, receipt_exact = None, False, False
    served = response.provider_metadata.get("model")
    header = transport.get("x-aihubmix-model")
    contract["probes"].append({
        "request_id": "r2-json-fidelity-p1",
        "streaming": bool(params.get("stream")),
        "transport_and_identity": {
            "http_status": transport.get("http_status"),
            "gateway_header_model": header, "served_body_model": served,
            "identity_matches_request": header == aihubmix_study.MODEL
                                         or served == aihubmix_study.MODEL,
            "finish_reason": response.finish_reason,
            "usage_reported": dict(response.usage),
            "reasoning_content_separated": bool(getattr(response, "reasoning_content", None))},
        "json_content_fidelity": {
            "valid_json_object": json_shape_ok, "receipt_value_exact": receipt_exact},
        "note": "transport/identity validity and JSON-content fidelity are separate verdicts"})
    contract["output_profile_effective"] = {
        "base_max_tokens": aihubmix_study.OUTPUT_PROFILE["base_max_tokens"],
        "complex_max_tokens": min(aihubmix_study.OUTPUT_PROFILE["complex_max_tokens"],
                                  accepted_ceiling),
        "ceiling_max_tokens": accepted_ceiling,
        "effort_default": "high", "effort_complex": "max"}
    schema = await port.describe_model(aihubmix_study.MODEL)
    contract["schema"] = schema
    contract["summary"] = {
        "accepted_ceiling": accepted_ceiling,
        "identity_ok": contract["probes"][0]["transport_and_identity"]["identity_matches_request"],
        "json_exact": receipt_exact,
        "finish": response.finish_reason,
        "usage": dict(response.usage)}
    atomic_json(OUT / "PROVIDER_CONTRACT.json", contract)
    print(json.dumps(contract["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
