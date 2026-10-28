"""Bounded Round02 protocol/effort study on the existing ModelPort and request ledger."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from ioabench.config.loader import load_workspace_env
from ioabench.errors import ModelUnsupportedError
from ioabench.hashing import canonical_sha256
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.v5.ai_generation.auxiliary_runtime import (
    AuxiliaryContract, AuxiliaryRouter, RequestUnresolved, classify_provider_failure, redact,
)
from ioabench.v5.ai_generation.model_routing import auxiliary_parameters
from ioabench.v5.evaluation import atomic_json
from compare_auxiliary_models import TOOL, assistant_message, checked_json, immutable, read

VERSION = "ioabench.v5.round02-provider-study/1.0.0"


def prepare(out):
    if read(out / "s1-completion/S1_RESULT.json")["status"] != "PASS":
        raise ValueError("S1 completion gate has not passed")
    models = [
        "gpt-6.1-sol", "glm-5.3-flash", "mimo-v2.6-pro", "claude-haiku-5-5",
        "mimo-v2.6-flash", "qwen3.8-flash", "deepseek-v4.1-flash-1017", "glm-5.3",
        "claude-opus-5-5", "claude-sonnet-5-5", "gpt-6-astra", "gemini-4-argon",
        "kimi-k3", "gpt-6-luna", "gemini-3.8-flash", "qwen3.8-max",
        "step-5-preview", "grok-4.7", "minimax-m3", "muse-spark-1.3",
    ]
    catalog = read(out / "MODEL_CATALOG.json")
    configs = []
    for model in models:
        schema = read(out / "schemas" / (model + ".json"))
        if not schema:
            continue
        protocol = ("anthropic.messages" if schema["vendor"] == "anthropic" else
                    "openai.responses" if schema["vendor"] == "openai" else "openai.chat_completions")
        entry = next(row for row in catalog if (row.get("model_id") or row.get("id")) == model)
        try:
            parameters = auxiliary_parameters(schema, protocol=protocol, output_budget=4096, catalog_entry=entry)
        except ModelUnsupportedError as exc:
            configs.append({"id": model + "--default", "model": model, "protocol": protocol,
                            "status": "BLOCKED_DOCUMENTATION", "reason": str(exc)})
            continue
        if schema["vendor"] == "anthropic":
            parameters["thinking"] = {"type": "adaptive"}
        configs.append({"id": model + "--default", "model": model, "protocol": protocol,
                        "parameters": parameters, "schema_sha256": canonical_sha256(schema),
                        "scope": "PROTOCOL_ONLY_NOT_ROLE_QUALIFICATION"})
    plan = {"version": VERSION, "configs": configs, "tasks": ["text", "json", "multiturn", "tool-loop"],
            "max_attempts_per_task": 1, "no_resend": True, "timeout_seconds": 180,
            "auth_or_unknown": "GLOBAL_STOP", "historical_unresolved_resends": 0,
            "R_two_nonoverlapping_batches": "AFTER_PROTOCOL_GATE", "S4_quality": "AFTER_PROTOCOL_GATE",
            "seed": 271020, "formal_accepted": False, "auditor_qualified": False}
    immutable(out / "PROTOCOL_PLAN.json", plan)
    return plan


class Study:
    def __init__(self, out, port):
        self.out, self.port = out, port
        self.catalog = read(out / "MODEL_CATALOG.json")
        self.stop_path = out / "STOP.json"
        if hasattr(port, "_requester"):
            transport = port._requester
            wire = out / "wire"
            wire.mkdir(exist_ok=True)
            self.sequence = len(list(wire.glob("*.json")))
            def record(method, path, body):
                self.sequence += 1
                target = wire / f"http-{self.sequence:05d}.json"
                row = {"at_utc": datetime.now(timezone.utc).isoformat(), "method": method,
                       "base_url": port.base_url, "path": path, "body": body,
                       "body_sha256": canonical_sha256(body)}
                started = time.monotonic()
                try:
                    payload = transport(method, path, body)
                    row["decoded_response"] = payload
                    return payload
                except Exception as exc:
                    row.update(error_type=type(exc).__name__, error=redact(str(exc)))
                    raise
                finally:
                    row["elapsed_ms"] = (time.monotonic() - started) * 1000
                    atomic_json(target, redact(row))
            port._requester = record

    async def invoke(self, config, directory, request_id, messages, *, tools=(), validate=None):
        if self.stop_path.exists():
            raise RuntimeError("study stopped; no new paid request permitted")
        entry = next(row for row in self.catalog if (row.get("model_id") or row.get("id")) == config["model"])
        contract = AuxiliaryContract(
            ModelProfile("aihubmix", config["model"], {"endpoint_family": config["protocol"]}, {}),
            config["parameters"], entry, str(self.out / "PROTOCOL_PLAN.json"), ("AUX_PROTOCOL_PROBE",))
        router = AuxiliaryRouter(self.port, [contract], self.catalog, directory, max_attempts_per_model=1)
        try:
            return await router.invoke("AUX_PROTOCOL_PROBE", request_id,
                                       ModelRequest(messages, {}, tools), validate=validate)
        except Exception as exc:
            category = classify_provider_failure(exc)
            if isinstance(exc, RequestUnresolved) or category in {"AUTH/PERMISSION", "MISSING_SECRET", "REQUEST_UNRESOLVED"}:
                atomic_json(self.stop_path, {"at_utc": datetime.now(timezone.utc).isoformat(),
                    "category": "REQUEST_UNRESOLVED" if isinstance(exc, RequestUnresolved) else category,
                    "model": config["model"], "request_id": request_id, "evidence": str(directory),
                    "error": redact(str(exc)), "action": "NO_RETRY_NO_REROUTE_STOP_ALL_PAID_TASKS"})
            raise

    async def protocol(self, config, batch="p1"):
        directory = self.out / "protocols" / config["id"] / batch
        result_path = directory / "RESULT.json"
        if result_path.exists():
            return read(result_path)
        row = {"config": config, "batch": batch, "started_utc": datetime.now(timezone.utc).isoformat(),
               "status": "NOT_RUN", "tasks": {name: "NOT_RUN" for name in ("text", "json", "multiturn", "tool-loop")}}
        token = canonical_sha256({"run": self.out.name, "config": config, "batch": batch})[:24]
        parameters = dict(config["parameters"])
        parameters.pop("response_format", None)
        parameters.pop("text", None)
        text_config = {**config, "parameters": parameters}
        current = "text"
        try:
            response = await self.invoke(text_config, directory / "model_io", batch + "-text",
                [{"role": "user", "content": "Reply only with this receipt: " + token}],
                validate=lambda r: _text(r, token))
            row["tasks"]["text"] = "PASS"
            current = "json"
            expected = {"receipt": token, "value": 42}
            await self.invoke(config, directory / "model_io", batch + "-json",
                [{"role": "user", "content": "Return exactly this JSON object: " + json.dumps(expected)}],
                validate=lambda r: checked_json(r, expected))
            row["tasks"]["json"] = "PASS"
            current = "multiturn"
            await self.invoke(config, directory / "model_io", batch + "-multiturn",
                [{"role": "user", "content": "Remember receipt " + token}, assistant_message(response),
                 {"role": "user", "content": "Return JSON with only receipt equal to the receipt above."}],
                validate=lambda r: checked_json(r, {"receipt": token}))
            row["tasks"]["multiturn"] = "PASS"
            current = "tool-loop"
            schema = read(self.out / "schemas" / (config["model"] + ".json"))
            entry = next(row for row in self.catalog if (row.get("model_id") or row.get("id")) == config["model"])
            auxiliary_parameters(schema, protocol=config["protocol"], for_tools=True, output_budget=4096,
                                 effort=_effort(config["parameters"]), catalog_entry=entry)
            messages = [{"role": "user", "content": "Receipt " + token +
                         '. Call echo_receipt once with value=42. After its result return exactly JSON {"received":42}.'}]
            first = await self.invoke(text_config, directory / "model_io", batch + "-tool-start", messages, tools=[TOOL])
            if len(first.tool_calls) != 1:
                raise ValueError("MODEL_QUALITY: missing single tool call")
            call = first.tool_calls[0]
            args = call["function"]["arguments"]
            args = json.loads(args) if isinstance(args, str) else args
            if call["function"]["name"] != "echo_receipt" or args != {"value": 42}:
                raise ValueError("MODEL_QUALITY: tool name/arguments mismatch")
            messages += [assistant_message(first), {"role": "tool", "tool_call_id": call["id"], "content": '{"stored":42}'}]
            await self.invoke(text_config, directory / "model_io", batch + "-tool-finish", messages, tools=[TOOL],
                              validate=lambda r: checked_json(r, {"received": 42}))
            row["tasks"]["tool-loop"] = "PASS"
            row["status"] = "PASS"
        except Exception as exc:
            row.update(status="PARTIAL" if "PASS" in row["tasks"].values() else "FAIL",
                       category=classify_provider_failure(exc), error_type=type(exc).__name__, error=redact(str(exc)))
            row["tasks"][current] = "FAIL"
        row["completed_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_json(result_path, row)
        return row


def _effort(parameters):
    return parameters.get("reasoning_effort", parameters.get("reasoning", parameters.get("output_config", {})).get("effort"))


def _text(response, expected):
    if response.text.strip() != expected:
        raise ValueError("MODEL_QUALITY: text receipt mismatch")


async def run(out, phase):
    plan = prepare(out)
    if phase == "prepare":
        return
    load_workspace_env(ROOT / ".env")
    port = AIHubMixAdapter(base_url="https://api.inferera.com/v1", stop_on_provider_error=True,
                           request_timeout=plan["timeout_seconds"])
    study = Study(out, port)
    configs = list(plan["configs"])
    batch = "p1"
    if phase == "protocol-followup":
        configs = []
        for model, protocol in (("minimax-m3", "anthropic.messages"), ("muse-spark-1.3", "openai.responses")):
            schema = read(out / "schemas" / (model + ".json"))
            entry = next(row for row in study.catalog if (row.get("model_id") or row.get("id")) == model)
            parameters = auxiliary_parameters(schema, protocol=protocol, output_budget=4096, catalog_entry=entry)
            if model == "minimax-m3":
                parameters["thinking"] = {"type": "adaptive"}
            configs.append({"id": model + "--native-default", "model": model, "protocol": protocol,
                            "parameters": parameters, "schema_sha256": canonical_sha256(schema),
                            "scope": "NEW_PROTOCOL_TASK_NOT_RETRY_OF_OLD_TASK"})
        immutable(out / "SUPPLEMENTAL_CONFIGS.json", configs)
        batch = "p1-native"
    random.Random(plan["seed"]).shuffle(configs)
    for config in configs:
        if study.stop_path.exists():
            break
        if config.get("status") == "BLOCKED_DOCUMENTATION":
            print(json.dumps(config), flush=True)
            continue
        result = await study.protocol(config, batch)
        print(json.dumps({"model": config["model"], "status": result["status"], "tasks": result["tasks"],
                          "category": result.get("category")}), flush=True)
    atomic_json(out / ("PROTOCOL_SUMMARY.json" if phase == "protocol" else "SUPPLEMENTAL_SUMMARY.json"), {"version": VERSION, "stop": read(study.stop_path) if study.stop_path.exists() else None,
        "planned": len(configs), "results": [read(p) for p in sorted((out / "protocols").glob("*/" + batch + "/RESULT.json"))]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--phase", choices=("prepare", "protocol", "protocol-followup"), required=True)
    args = parser.parse_args()
    asyncio.run(run(args.out, args.phase))


if __name__ == "__main__":
    main()
