"""Two-turn auxiliary tool protocol probes and an explicit provider-schema failover control."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelRequest
from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryRouter, qualified_contracts
from ioabench.v5.evaluation import atomic_json, writer_lock
from routed_t321_data_factory_s1 import _load_api_key

TOOL = {"type": "function", "function": {"name": "echo_receipt", "description": "Store a local integer receipt.",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["value"],
                   "properties": {"value": {"type": "integer"}}}}}


def checked_result(response):
    text = (response.text or "").strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        valid = json.loads(text) == {"received": 42}
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("MODEL_QUALITY: tool receipt was not correctly used")


async def probe(output: Path, preflight: Path, models: list[str], schema_failover: bool = False):
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result_path = output / "TOOL_PREFLIGHT.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        for name, expected in result["evidence_sha256"].items():
            if hashlib.sha256((output / name).read_bytes()).hexdigest() != expected:
                raise ValueError("tool probe evidence changed")
        return result
    catalog, contracts, endpoint = qualified_contracts(preflight, workspace=ROOT,
        role="AUX_PROTOCOL_PROBE", model_ids=models, for_tools=True)
    port = AIHubMixAdapter(api_key=_load_api_key(), base_url=endpoint, stop_on_provider_error=True, request_timeout=180)
    rows = []
    for contract in contracts:
        directory = output / contract.profile.model_id
        router = AuxiliaryRouter(port, [contract], catalog, directory)
        messages = [{"role": "user", "content": "Call echo_receipt once with value=42. After its result, return exactly JSON {\"received\":42}."}]
        try:
            first = await router.invoke("AUX_PROTOCOL_PROBE", "tool-start", ModelRequest(messages, {}, [TOOL]))
            if len(first.tool_calls) != 1:
                raise ValueError("MODEL_QUALITY: expected one real tool call")
            call = first.tool_calls[0]
            arguments = call["function"]["arguments"]
            arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            if call["function"]["name"] != "echo_receipt" or arguments != {"value": 42}:
                raise ValueError("MODEL_QUALITY: tool name/arguments mismatch")
            assistant = {"role": "assistant", "content": first.text or "", "tool_calls": list(first.tool_calls)}
            if first.reasoning_content is not None:
                assistant["reasoning_content"] = first.reasoning_content
            if first.reasoning_details:
                assistant["reasoning_details"] = first.reasoning_details
            messages.extend([assistant, {"role": "tool", "tool_call_id": call["id"], "content": '{"stored":42}'}])
            await router.invoke("AUX_PROTOCOL_PROBE", "tool-finish", ModelRequest(messages, {}, [TOOL]), validate=checked_result)
            rows.append({"model_id": contract.profile.model_id, "status": "TOOL_LOOP_PASS",
                         "real_tool_calls": 1, "parameters": dict(contract.parameters)})
        except Exception as exc:
            rows.append({"model_id": contract.profile.model_id, "status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)})
    failover = {"status": "NOT_RUN"}
    if schema_failover and len(contracts) >= 2:
        first = replace(contracts[0], parameters={**contracts[0].parameters,
            next(key for key in ("max_tokens", "max_completion_tokens") if key in contracts[0].parameters): "deliberately-invalid-negative-control"})
        router = AuxiliaryRouter(port, [first, contracts[1]], catalog, output / "schema-failover")
        try:
            response = await router.invoke("AUX_PROTOCOL_PROBE", "explicit-schema-negative", ModelRequest([
                {"role": "user", "content": 'Return exactly JSON {"received":42}.'}], {}), validate=checked_result)
            failover = {"status": "PASS" if response.model_id == contracts[1].profile.model_id else "UNEXPECTED_FIRST_MODEL_ACCEPTANCE",
                "served_model_id": response.model_id, "negative_control": "deliberately invalid output-limit type; no real outage claimed"}
        except Exception as exc:
            failover = {"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)}
    events = [json.loads(line) for path in output.rglob("AIHUBMIX_ATTEMPTS.jsonl")
              for line in path.read_text(encoding="utf-8").splitlines()]
    finished = [row for row in events if row["event"] == "REQUEST_FINISHED"]
    result = {"status": "TOOL_PROTOCOL_PASS" if all(row["status"] == "TOOL_LOOP_PASS" for row in rows) else "PARTIAL",
        "rows": rows, "schema_failover": failover, "source_sha256": source_hash,
        "completion_attempts": sum(row["event"] == "REQUEST_STARTED" for row in events),
        "usage": {key: sum(int((row.get("usage") or {}).get(key) or 0) for row in finished)
                  for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "estimated_usd": sum((row.get("cost") or {}).get("amount") or 0 for row in finished),
        "failed_usage": "UNKNOWN unless returned", "formal_SUT_changed": False}
    result["evidence_sha256"] = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output.rglob("*") if path.is_file() and path.name not in {"TOOL_PREFLIGHT.json", ".writer.lock"}}
    atomic_json(result_path, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--models", required=True, nargs="+")
    parser.add_argument("--schema-failover", action="store_true")
    args = parser.parse_args()
    with writer_lock(args.out):
        result = asyncio.run(probe(args.out, args.preflight, args.models, args.schema_failover))
    print(json.dumps({key: result[key] for key in ("status", "rows", "schema_failover", "completion_attempts", "usage", "estimated_usd")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "TOOL_PROTOCOL_PASS" else 1)
