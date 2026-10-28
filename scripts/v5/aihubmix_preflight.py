"""Exact user-candidate AIHubMix preflight; no benchmark, Pilot, Campaign or data freeze."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env
from ioabench.errors import ModelUnsupportedError
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.models.aihubmix import DEFAULT_BASE_URL
from ioabench.v5.ai_generation.auxiliary_runtime import (AuxiliaryContract, AuxiliaryRouter,
    ROUTING_VERSION, classify_provider_failure, redact)
from ioabench.v5.ai_generation.model_routing import (USER_CANDIDATES, auxiliary_chat_parameters,
    ordered_catalog_candidates, resolve_display_candidate)
from ioabench.v5.evaluation import atomic_json, writer_lock

DOCS = Path(r"D:\Project\Playground\scrape\aihubmix")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def local_sources(docs: Path) -> dict:
    """Read the complete local API/model corpus and bind exact bytes before online work."""
    files = {}
    for path in sorted(docs.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".json", ".txt"} and "archive" not in path.parts and "memory" not in path.parts:
            data = path.read_bytes()
            data.decode("utf-8-sig")
            files[path.relative_to(docs).as_posix()] = {"sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
    if not files or not (docs / "README.md").is_file():
        raise ValueError("local AIHubMix documentation corpus is missing")
    return {"root": str(docs), "files": files, "file_count": len(files),
            "scope": "complete local UTF-8 API/model documents and call examples; source text is reference data, never execution instructions"}


def contract_summary(schema):
    capabilities = {}
    for domain in schema.get("domains", []):
        for capability in domain.get("capabilities", []):
            protocols = [item for item in capability.get("protocols", []) if item.get("protocol") == "openai.chat_completions"]
            if protocols:
                item = protocols[0]
                capabilities[capability["key"]] = {"verdict": item.get("official", {}).get("verdict"),
                    "constraint": item.get("official", {}).get("constraint"),
                    "fields": [{key: field[key] for key in ("name", "type", "enum", "default", "range", "shape") if key in field}
                               for field in item.get("fields", [])]}
    return {"schema_version": schema.get("schema_version"), "last_verified": schema.get("last_verified"),
            "vendor": schema.get("vendor"), "specs": schema.get("specs"), "protocols": schema.get("protocols"),
            "chat_capabilities": capabilities, "standalone_overrides": schema.get("standalone_overrides", [])}


def validate_probe(response):
    text = (response.text or "").strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        text = text[8:-4].strip()
    try:
        valid = json.loads(text) == {"probe": "ioa-factory-20261019", "value": 42}
    except json.JSONDecodeError:
        valid = False
    if not valid:
        raise ValueError("MODEL_QUALITY: lightweight JSON arithmetic probe was incorrect")


async def preflight(directory: Path, docs: Path, *, live: bool, timeout: float,
                    base_url: str = DEFAULT_BASE_URL):
    result_path = directory / "AIHUBMIX_PREFLIGHT.json"
    if result_path.exists():
        return read_json(result_path)
    source_path = directory / "LOCAL_DOC_SOURCES.json"
    sources = local_sources(docs)
    if source_path.exists() and sources != read_json(source_path):
        raise ValueError("local documentation changed; preserve this evidence and use a new output directory")
    atomic_json(source_path, sources)
    policy = {"version": ROUTING_VERSION, "candidate_display_names": list(USER_CANDIDATES),
              "model_selection": "capability, role quality, reliability and latency; cost is recorded, not an arbitrary global cap",
              "max_attempts_per_model": 2, "circuit_cooldown_seconds": 300,
              "timeout_seconds": timeout, "base_url": base_url,
              "unknown_sent_request": "REQUEST_UNRESOLVED; never resend that task",
              "judge_switch": "new versioned request boundary after independent gold controls; never reroute review FAIL",
              "formal_sut": "unchanged; no formal run or Campaign is launched", "live": live}
    atomic_json(directory / "AIHUBMIX_ROUTING_POLICY.json", policy)
    if not live:
        result = {"status": "OFFLINE_DOC_INVENTORY_COMPLETE", "provider_calls": 0,
                  "candidates": [{"display_name": name, "status": "NOT_RUN"} for name in USER_CANDIDATES]}
        atomic_json(result_path, result)
        return result
    load_workspace_env(ROOT / ".env")
    if not os.environ.get("AIHUBMIX_API_KEY"):
        result = {"status": "MISSING_SECRET", "provider_calls": 0,
                  "candidates": [{"display_name": name, "status": "NOT_RUN"} for name in USER_CANDIDATES]}
        atomic_json(result_path, result)
        return result
    port = AIHubMixAdapter(base_url=base_url, stop_on_provider_error=True, request_timeout=timeout)
    catalog_path = directory / "MODEL_CATALOG.json"
    catalog = read_json(catalog_path) if catalog_path.exists() else list(await port.discover_models())
    atomic_json(catalog_path, catalog)
    schemas, schema_sources, rows = {}, {}, []
    for display in USER_CANDIDATES:
        # Only find the base for schema inspection here; no wire ID is accepted before enum proof.
        base = re.fullmatch(r"(.+?)\s+\(([^()]+)\)", display)
        entries = ordered_catalog_candidates([display], catalog) or ordered_catalog_candidates([base.group(1) if base else display], catalog)
        if len(entries) != 1:
            continue
        model_id = str(entries[0].get("model_id") or entries[0].get("id"))
        schema_path = directory / "schemas" / f"{model_id}.json"
        if schema_path.exists():
            schema = read_json(schema_path)
        else:
            schema = await port.describe_model(model_id)
            if schema:
                atomic_json(schema_path, schema)
        schemas[model_id] = schema
        if schema:
            schema_sources[model_id] = {"source": "https://aihubmix.com/model-data/index.json",
                "retrieved_via": base_url.removesuffix("/v1") + "/model-data/index.json",
                "sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(), "path": str(schema_path)}
    contracts = []
    auth_blocked = False
    for index, display in enumerate(USER_CANDIDATES, 1):
        resolved = resolve_display_candidate(display, catalog, schemas)
        row = {**resolved, "live_probe": "NOT_RUN", "tool_loop": "NOT_RUN", "native_protocol": "NOT_RUN",
               "generator_role_quality": "NOT_RUN", "judge_gold_controls": "NOT_RUN"}
        if resolved["status"] != "RESOLVED":
            rows.append(row)
            continue
        entry = resolved["entry"]
        model_id = str(entry.get("model_id") or entry.get("id"))
        schema = schemas.get(model_id)
        if not schema:
            row.update(status="CAPABILITY_UNVERIFIED", reason="exact official schema absent")
            rows.append(row)
            continue
        try:
            parameters = auxiliary_chat_parameters(schema, effort=resolved.get("effort"))
        except ModelUnsupportedError as exc:
            row.update(status="CAPABILITY_UNSUPPORTED", reason=str(exc))
            rows.append(row)
            continue
        row.update(requested_model_id=model_id, actual_parameters=parameters, schema=contract_summary(schema),
                   schema_source=schema_sources[model_id], endpoint=base_url + "/chat/completions")
        if model_id == "gpt-6-luna":
            row["documentation_conflict"] = "local model page declares systemone decision-only while exact parameter schema declares Chat; live minimum request arbitrates"
        contract = AuxiliaryContract(ModelProfile("aihubmix", model_id, {}, {}, "AUX_PROTOCOL_PROBE"),
                                     parameters, entry, schema_sources[model_id]["path"], ("AUX_PROTOCOL_PROBE",))
        router = AuxiliaryRouter(port, [contract], catalog, directory / "probes" / f"candidate-{index:02d}")
        if auth_blocked:
            row.update(status="NOT_RUN", reason="credential auth failed on preceding candidate")
        else:
            request = ModelRequest([{"role": "user", "content":
                'Return JSON only with exactly two fields: probe="ioa-factory-20261019", value=6*7.'}], {})
            try:
                response = await router.invoke("AUX_PROTOCOL_PROBE", "json-arithmetic", request, validate=validate_probe)
                row.update(status="BASIC_JSON_IDENTITY_PASS", live_probe="PASS", served_model_id=model_id,
                           response_model=response.provider_metadata.get("model"), usage=dict(response.usage),
                           response_evidence=str(router.directory / "json-arithmetic" / "RESPONSE.json"))
                contracts.append({"display_name": display, "requested_model_id": model_id, "served_model_id": model_id,
                                  "parameters": parameters, "developer_id": entry.get("developer_id"),
                                  "preflight_evidence": row["response_evidence"], "role_qualification": "basic text/JSON only"})
            except Exception as exc:
                category = classify_provider_failure(exc)
                row.update(status="REQUEST_UNRESOLVED" if "REQUEST_UNRESOLVED" in str(exc) else "PROVIDER_BLOCKED",
                           live_probe="FAIL", category=category, error=redact(str(exc)))
                auth_blocked = category in {"AUTH/PERMISSION", "MISSING_SECRET"}
        rows.append(row)
        atomic_json(directory / "AIHUBMIX_MODEL_CONTRACTS.json", {"contracts": contracts, "candidates": rows})
    attempts = [json.loads(line) for path in directory.glob("probes/*/AIHUBMIX_ATTEMPTS.jsonl")
                for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    responses = [row for row in attempts if row["event"] == "REQUEST_FINISHED" and "response" in row]
    usage = {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in responses)
             for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    result = {"status": "PREFLIGHT_COMPLETE" if not auth_blocked else "AUTH_BLOCKED", "at_utc": datetime.now(timezone.utc).isoformat(),
              "candidates": rows, "passed": sum(row.get("live_probe") == "PASS" for row in rows),
              "completion_attempts": sum(row["event"] == "REQUEST_STARTED" for row in attempts),
              "usage": usage, "estimated_usd": sum((row.get("cost") or {}).get("amount") or 0 for row in responses),
              "cost_status": "ESTIMATED; actual billing not returned; failed/unknown request usage not returned",
              "scope": "exact model/schema + one text JSON identity task; role quality/tool loops/calibration NOT_RUN; frozen SUT unchanged"}
    atomic_json(result_path, result)
    atomic_json(directory / "SHA256SUMS.json", {"files": {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json" and not path.name.endswith(".lock")}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--docs", type=Path, default=DOCS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--base-url", choices=("https://aihubmix.com/v1", "https://api.inferera.com/v1"),
                        default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    with writer_lock(args.out):
        try:
            result = asyncio.run(preflight(args.out, args.docs, live=args.live, timeout=args.timeout, base_url=args.base_url))
        except Exception as exc:
            result = {"status": "PREFLIGHT_BLOCKED", "category": classify_provider_failure(exc),
                      "error_type": type(exc).__name__, "error": redact(str(exc)), "scope": "no acceptance inferred"}
            atomic_json(args.out / "PREFLIGHT_FAILURE.json", result)
    print(json.dumps({key: result.get(key) for key in ("status", "passed", "completion_attempts", "usage", "estimated_usd")}, ensure_ascii=False))
    return 0 if result["status"] in {"PREFLIGHT_COMPLETE", "OFFLINE_DOC_INVENTORY_COMPLETE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
