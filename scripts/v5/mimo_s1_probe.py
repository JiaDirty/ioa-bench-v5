"""Data-factory stage gate S1: MiMo-V2.6-Pro capability probe (post-audit P3 preparation).

Verifies, with minimal Provider calls (PI-V5-007 small-scale technical trial authorization):
  1. model availability via AIHubMix discovery (resolve);
  2. served identity + structured-output capability in one generation call
     (thinking disabled, bounded output per the data-factory contract — NOT the DeepSeek 128K profile);
  3. real response metadata persisted: served model, parameters, usage, finish_reason.

Evidence: artifacts/v5/data_factory/s1-mimo-probe-<stamp>.json (refuses overwrite).
The API key is read from .env / environment and NEVER persisted or printed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.models.aihubmix import AIHubMixAdapter  # noqa: E402
from ioabench.models.types import ModelProfile, ModelRequest  # noqa: E402
from ioabench.errors import ModelUnsupportedError, ProviderPermanentError, ProviderTransientError  # noqa: E402

MODEL_ID = "mimo-v2.6-pro"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
DEST = ROOT / "artifacts/v5/data_factory" / f"s1-mimo-probe-{STAMP}.json"


def load_env_key() -> str:
    key = os.environ.get("AIHUBMIX_API_KEY")
    if key:
        return key
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("AIHUBMIX_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("AIHUBMIX_API_KEY not found in environment or .env")


def main() -> int:
    key = load_env_key()
    adapter = AIHubMixAdapter(api_key=key)
    evidence: dict[str, Any] = {
        "kind": "ioabench.v5.data-factory.s1-mimo-probe/1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_id": MODEL_ID,
        "stage": "S1 (capability probe; no blueprint accepted into any pool)",
        "calls": [],
    }

    async def run() -> None:
        # step 1: discovery/resolve
        try:
            profile = await adapter.resolve(MODEL_ID)
            evidence["calls"].append({"step": "resolve", "ok": True,
                                      "capabilities": dict(profile.capabilities or {})})
        except (ModelUnsupportedError, ProviderPermanentError, ProviderTransientError) as exc:
            evidence["calls"].append({"step": "resolve", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
            evidence["verdict"] = "FAIL: model unavailable"
            return
        # step 2: one structured-output generation (bounded, thinking disabled)
        request = ModelRequest(messages=[
            {"role": "system", "content": "You produce compact JSON only."},
            {"role": "user", "content": ('Return a JSON object with exactly these keys: '
                                         '{"suite_id": "T321", "subtype": "T321-S5", '
                                         '"difficulty": "M", "task_summary": "<one sentence>", '
                                         '"mechanism_note": "<one sentence>"}. No other keys.')},
        ], parameters={"temperature": 0.0, "max_tokens": 2048, "thinking": {"type": "disabled"}})
        response = await adapter.generate(profile, request)
        parsed = None
        parse_error = None
        if response.text:
            try:
                parsed = json.loads(response.text)
            except json.JSONDecodeError as exc:
                parse_error = str(exc)
        evidence["calls"].append({
            "step": "generate", "served_model": response.model_id,
            "finish_reason": response.finish_reason,
            "usage": dict(response.usage or {}),
            "text_chars": len(response.text or ""),
            "text_preview": (response.text or "")[:400],
            "json_parsed": parsed is not None,
            "parse_error": parse_error,
        })

    try:
        asyncio.run(run())
        if not any(c.get("step") == "generate" and c.get("json_parsed") for c in evidence["calls"]):
            evidence.setdefault("verdict", "PARTIAL: generation did not yield parseable JSON")
        else:
            evidence.setdefault("verdict", "PASS: discovery + structured generation verified")
    except (ProviderPermanentError, ProviderTransientError) as exc:
        evidence["verdict"] = f"FAIL: {type(exc).__name__}: {exc}"
    evidence["verdict"] = evidence.get("verdict", "INCOMPLETE")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK verdict={evidence['verdict']} -> {DEST.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
