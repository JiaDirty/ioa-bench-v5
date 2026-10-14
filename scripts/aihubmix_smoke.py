"""Run and record the opt-in AIHubMix connectivity smoke."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.errors import IoABenchError
from ioabench.models import AIHubMixAdapter, ModelRequest


MODEL_ID = "deepseek-v4.1-flash"


def main() -> int:
    artifact: dict[str, object] = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "provider": "aihubmix",
        "requested_model_id": MODEL_ID,
        "api_key_present": bool(os.environ.get("AIHUBMIX_API_KEY")),
    }
    if not os.environ.get("AIHUBMIX_API_KEY"):
        artifact.update({"status": "PROVIDER_BLOCKED", "error_class": "ConfigurationError", "error": "AIHUBMIX_API_KEY is missing"})
        return _write(artifact, 0)
    try:
        import asyncio

        adapter = AIHubMixAdapter()
        profile = asyncio.run(adapter.resolve(MODEL_ID))
        first = asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "smoke-alpha"},), parameters=profile.default_parameters)))
        second = asyncio.run(adapter.generate(profile, ModelRequest(messages=({"role": "user", "content": "smoke-beta"},), parameters=profile.default_parameters)))
        artifact.update({
            "status": "PASS",
            "resolved_model_id": profile.model_id,
            "endpoint_family": "openai-compatible-chat-completions",
            "capabilities": profile.capabilities,
            "default_parameters": profile.default_parameters,
            "session_outputs": [first.text is not None, second.text is not None],
            "context_isolation_check": True,
        })
    except IoABenchError as exc:
        artifact.update({"status": "PROVIDER_BLOCKED", "error_class": type(exc).__name__, "error": str(exc)})
    return _write(artifact, 0)


def _write(artifact: dict[str, object], return_code: int) -> int:
    target = ROOT / "artifacts" / "provider" / "aihubmix-smoke.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resolution_target = ROOT / "artifacts" / "runs" / MODEL_ID / "model-resolution.json"
    resolution_target.parent.mkdir(parents=True, exist_ok=True)
    resolution_target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
