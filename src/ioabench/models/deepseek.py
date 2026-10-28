"""Direct DeepSeek OpenAI-compatible adapter for versioned exploratory runs."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from http.client import HTTPException
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ioabench.errors import (ConfigurationError, ModelUnsupportedError, ProviderPermanentError,
                            ProviderTransientError, ProviderRequestUnresolved)
from .aihubmix import _response_from_payload
from .types import ModelProfile, ModelRequest, normalize_request

JsonRequester = Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]]


class DeepSeekAdapter:
    """Direct adapter; never claims an AIHubMix or formal-model identity."""

    def __init__(self, *, api_key: str | None = None,
                 base_url: str = "https://api.deepseek.com",
                 requester: JsonRequester | None = None,
                 request_timeout: float = 900.0) -> None:
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = base_url.rstrip("/")
        if self.base_url not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
            raise ValueError("DeepSeek credentials require the official HTTPS endpoint")
        self._requester = requester or self._request_json
        self._request_timeout = request_timeout
        self.stop_on_provider_error = True

    async def discover_models(self) -> tuple[Mapping[str, Any], ...]:
        payload = await asyncio.to_thread(self._requester, "GET", "/models", {})
        items = payload.get("data", ()) if isinstance(payload, Mapping) else ()
        if not isinstance(items, list):
            raise ProviderPermanentError("DeepSeek model catalog has invalid data")
        return tuple(item for item in items if isinstance(item, Mapping))

    async def resolve(self, model_id: str) -> ModelProfile:
        models = await self.discover_models()
        item = next((item for item in models if item.get("id") == model_id), None)
        if item is None:
            raise ModelUnsupportedError(f"DeepSeek model is unavailable: {model_id}")
        return ModelProfile("deepseek", model_id, dict(item.get("capabilities") or {}),
                            dict(item.get("default_parameters") or {}))

    async def generate(self, profile: ModelProfile, request: ModelRequest):
        if profile.provider != "deepseek":
            raise ProviderPermanentError(f"unsupported provider profile: {profile.provider}")
        request = normalize_request(request)
        body: dict[str, Any] = {"model": profile.model_id, "messages": list(request.messages),
                                **dict(request.parameters)}
        if request.tools:
            body["tools"] = list(request.tools)
        payload = await asyncio.to_thread(self._requester, "POST", "/chat/completions", body)
        try:
            return _response_from_payload(payload, profile.model_id)
        except (ValueError, TypeError, ProviderPermanentError) as exc:
            error = ProviderRequestUnresolved("DeepSeek response envelope incomplete; no resend")
            error.transport_metadata = dict(payload.get("_transport") or {})
            raise error from exc

    def _request_json(self, method: str, path: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self._api_key:
            raise ConfigurationError("DEEPSEEK_API_KEY is required for provider calls")
        data = json.dumps(body).encode("utf-8") if method == "POST" else None
        request = Request(self.base_url + path, data=data, method=method,
                         headers={"Content-Type": "application/json"})
        request.add_unredirected_header("Authorization", f"Bearer {self._api_key}")
        started, raw = time.monotonic(), b""
        metadata = {"provider": "deepseek", "endpoint": self.base_url + path,
                    "method": method, "http_status": None}
        try:
            with urlopen(request, timeout=self._request_timeout) as response:
                metadata.update(http_status=response.status, headers={key.lower(): value
                    for key, value in response.headers.items() if key.lower() in {
                        "x-request-id", "x-ds-request-id", "date", "content-type", "cf-ray"}})
                raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("non-object response")
        except HTTPError as exc:
            metadata["http_status"] = exc.code
            if exc.code == 404:
                error = ModelUnsupportedError(f"DeepSeek endpoint or model unavailable: HTTP {exc.code}")
            elif exc.code == 429 or exc.code >= 500:
                error = ProviderTransientError(f"DeepSeek transient HTTP {exc.code}")
            else:
                error = ProviderPermanentError(f"DeepSeek HTTP {exc.code}")
            error.http_status, error.transport_metadata = exc.code, metadata
            raise error from exc
        except (OSError, HTTPException, UnicodeError, ValueError) as exc:
            raw = getattr(exc, "partial", raw)
            preview = raw.decode("utf-8", errors="replace").replace(self._api_key, "[REDACTED]")
            metadata.update(body_sha256=hashlib.sha256(raw).hexdigest(), body_bytes=len(raw),
                            body_preview=re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", preview[:8192]),
                            elapsed_seconds=time.monotonic() - started)
            error_type = ProviderRequestUnresolved if method == "POST" else ProviderTransientError
            error = error_type(f"DeepSeek transport/body failure: {type(exc).__name__}; no automatic resend")
            error.http_status, error.transport_metadata = metadata["http_status"], metadata
            raise error from exc
        metadata.update(body_sha256=hashlib.sha256(raw).hexdigest(), body_bytes=len(raw),
                        elapsed_seconds=time.monotonic() - started)
        return {**payload, "_transport": metadata}
