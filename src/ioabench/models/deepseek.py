"""Direct DeepSeek OpenAI-compatible adapter for versioned exploratory runs."""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ioabench.errors import ConfigurationError, ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
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
        self._requester = requester or self._request_json
        self._request_timeout = request_timeout

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
        return _response_from_payload(payload, profile.model_id)

    def _request_json(self, method: str, path: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self._api_key:
            raise ConfigurationError("DEEPSEEK_API_KEY is required for provider calls")
        data = json.dumps(body).encode("utf-8") if method == "POST" else None
        request = Request(self.base_url + path, data=data, method=method,
                         headers={"Authorization": f"Bearer {self._api_key}",
                                  "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self._request_timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise ModelUnsupportedError(f"DeepSeek endpoint or model unavailable: HTTP {exc.code}") from exc
            if exc.code == 429 or exc.code >= 500:
                raise ProviderTransientError(f"DeepSeek transient HTTP {exc.code}") from exc
            raise ProviderPermanentError(f"DeepSeek HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise ProviderTransientError(f"DeepSeek transport failure: {type(exc).__name__}") from exc
        if not isinstance(payload, Mapping):
            raise ProviderPermanentError("DeepSeek returned a non-object response")
        return payload
