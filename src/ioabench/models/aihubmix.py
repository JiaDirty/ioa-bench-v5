from __future__ import annotations
import asyncio
from collections.abc import Callable, Mapping
import json
import os
import re
import shutil
import time
import subprocess
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ioabench.errors import ConfigurationError, ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
from .types import ModelProfile, ModelRequest, ModelResponse, normalize_request

JsonRequester = Callable[[str, str, Mapping[str, Any]], Mapping[str, Any]]


class AIHubMixAdapter:
    def __init__(self, *, api_key: str | None = None, base_url: str = "https://aihubmix.com/v1", fallback_base_url: str = "https://api.inferera.com/v1", requester: JsonRequester | None = None, request_timeout: float = 900.0, stop_on_provider_error: bool = False) -> None:
        self._api_key = api_key or os.environ.get("AIHUBMIX_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.fallback_base_url = fallback_base_url.rstrip("/")
        self._requester = requester or self._request_json
        # Bounded per-request wait. Sized for the 128K output ceiling (v1.1.2): a legitimate long
        # thinking turn may run for minutes, but a pathological one must not stall the batch.
        self._request_timeout = request_timeout
        self.stop_on_provider_error = stop_on_provider_error
        self._schema_index: Mapping[str, Any] | None = None
        self._schemas: dict[str, Mapping[str, Any] | None] = {}

    async def describe_model(self, model_id: str) -> Mapping[str, Any] | None:
        """Fetch the official per-model wire contract; opt-in for auxiliary calls only."""
        if model_id not in self._schemas:
            if self._schema_index is None:
                self._schema_index = await asyncio.to_thread(
                    self._requester, "GET", "/model-data/index.json", {})
            entry = next((item for item in self._schema_index.get("models", [])
                          if item.get("id") == model_id), None)
            schema = None
            if entry is not None:
                path = str(entry.get("path", ""))
                if not re.fullmatch(r"models/[A-Za-z0-9_%./-]+\.json", path) or ".." in path:
                    raise ProviderPermanentError("invalid official model schema path")
                schema = await asyncio.to_thread(self._requester, "GET", "/model-data/" + path, {})
                if schema.get("model_id") != model_id:
                    raise ProviderPermanentError("official schema model identity mismatch")
            self._schemas[model_id] = schema
        return self._schemas[model_id]

    async def resolve(self, model_id: str) -> ModelProfile:
        if not model_id:
            raise ValueError("model_id is required")
        try:
            payload = await asyncio.to_thread(self._requester, "GET", "/models", {})
        except ProviderTransientError:
            if self.stop_on_provider_error:
                raise
            payload = await asyncio.to_thread(self._requester, "GET", "/api/v1/models", {})
        items = _model_items(payload)
        match = next((item for item in items if item.get("id") == model_id or item.get("model_id") == model_id), None)
        if match is None and not self.stop_on_provider_error:
            payload = await asyncio.to_thread(self._requester, "GET", "/api/v1/models", {})
            match = next((item for item in _model_items(payload) if item.get("id") == model_id or item.get("model_id") == model_id), None)
        if match is not None:
            capabilities = dict(match.get("capabilities") or {})
            for key in ("features", "types", "endpoints", "input_modalities", "output_modalities"):
                if key in match:
                    capabilities[key] = match[key]
            return ModelProfile("aihubmix", model_id, capabilities, dict(match.get("default_parameters") or {}))
        raise ModelUnsupportedError(f"AIHubMix model is unavailable: {model_id}")

    async def discover_models(self) -> tuple[Mapping[str, Any], ...]:
        """Return exact authenticated model IDs enriched with the detailed live catalog."""
        try:
            payload = await asyncio.to_thread(self._requester, "GET", "/models", {})
        except ProviderTransientError:
            if self.stop_on_provider_error:
                raise
            payload = await asyncio.to_thread(self._requester, "GET", "/api/v1/models", {})
        models = _model_items(payload)
        try:
            detail_payload = await asyncio.to_thread(self._requester, "GET", "/api/v1/models", {})
        except ProviderTransientError:
            if self.stop_on_provider_error:
                raise
            return models
        try:
            details = {str(item.get("model_id") or item.get("id")): item
                       for item in _model_items(detail_payload)}
        except ProviderPermanentError:
            if self.stop_on_provider_error:
                raise
            return models
        return tuple({**dict(details.get(str(item.get("model_id") or item.get("id")), {})), **dict(item)}
                     for item in models)

    async def generate(self, profile: ModelProfile, request: ModelRequest) -> ModelResponse:
        if profile.provider != "aihubmix":
            raise ProviderPermanentError(f"unsupported provider profile: {profile.provider}")
        request = normalize_request(request)
        body: dict[str, Any] = {"model": profile.model_id, "messages": list(request.messages), **dict(request.parameters)}
        if request.tools:
            body["tools"] = list(request.tools)
        payload = await asyncio.to_thread(self._requester, "POST", "/chat/completions", body)
        return _response_from_payload(payload, profile.model_id)

    def _request_json(self, method: str, path: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        deadline = time.monotonic() + self._request_timeout
        if self.stop_on_provider_error:
            return self._request_json_once(method, path, body, deadline=deadline)
        last_error: Exception | None = None
        for attempt in range(3):
            if deadline <= time.monotonic():
                break
            try:
                return self._request_json_once(method, path, body, deadline=deadline)
            except ProviderTransientError as exc:
                last_error = exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(1.5 * (attempt + 1), remaining))
        if deadline <= time.monotonic():
            raise ProviderTransientError(
                f"AIHubMix request deadline exceeded ({self._request_timeout:g}s): {last_error}") from last_error
        raise last_error

    def _request_json_once(self, method: str, path: str, body: Mapping[str, Any],
                           *, deadline: float | None = None) -> Mapping[str, Any]:
        if not self._api_key:
            raise ConfigurationError("AIHUBMIX_API_KEY is required for provider calls")
        deadline = deadline if deadline is not None else time.monotonic() + self._request_timeout
        base_urls = ((self.base_url,) if self.stop_on_provider_error
                     else tuple(dict.fromkeys((self.base_url, self.fallback_base_url))))
        if os.name == "nt" and shutil.which("curl.exe"):
            curl_error: Exception | None = None
            for base_url in base_urls:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    curl_payload = _curl_json(base_url, method, path, body, self._api_key, remaining)
                    if curl_payload is not None:
                        return curl_payload
                    if self.stop_on_provider_error:
                        raise ProviderTransientError("AIHubMix curl returned no valid HTTP response")
                except ProviderTransientError as exc:
                    if self.stop_on_provider_error:
                        raise
                    curl_error = exc
            if curl_error is not None and time.monotonic() >= deadline:
                raise curl_error
        data = json.dumps(body).encode("utf-8") if method == "POST" else None
        decoded = None
        last_error: Exception | None = None
        for base_url in base_urls:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last_error = TimeoutError("AIHubMix request deadline exceeded")
                break
            request = Request(_request_url(base_url, path), data=data, method=method, headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=remaining) as response:
                    decoded = json.loads(response.read().decode("utf-8"))
                    if isinstance(decoded, dict):
                        decoded["transport_metadata"] = _response_headers(response.headers)
                last_error = None
                break
            except HTTPError as exc:
                # must precede URLError: HTTPError is a URLError subclass, so the
                # reverse order would misclassify every HTTP status as transient
                try:
                    body = exc.read().decode("utf-8", "ignore").strip()[:240]
                except OSError:
                    body = ""
                if exc.code == 429 or exc.code >= 500:
                    raise ProviderTransientError(f"AIHubMix transient HTTP {exc.code} {body}") from exc
                if exc.code == 404:
                    raise ModelUnsupportedError(f"AIHubMix endpoint or model is unavailable {body}") from exc
                raise ProviderPermanentError(f"AIHubMix HTTP {exc.code} {body}") from exc
            except URLError as exc:
                last_error = exc
                continue
            except (TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                break
        if last_error is not None:
            if self.stop_on_provider_error:
                raise ProviderTransientError(
                    f"AIHubMix request failed ({type(last_error).__name__}: {last_error})") from last_error
            curl_error: Exception | None = None
            for base_url in dict.fromkeys((self.base_url, self.fallback_base_url)):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    curl_payload = _curl_json(base_url, method, path, body, self._api_key, remaining)
                    if curl_payload is not None:
                        return curl_payload
                except ProviderTransientError as exc:
                    curl_error = exc
            if curl_error is not None:
                raise curl_error from last_error
            if time.monotonic() >= deadline:
                raise ProviderTransientError(
                    f"AIHubMix request deadline exceeded ({self._request_timeout:g}s)") from last_error
            raise ProviderTransientError(
                f"AIHubMix request failed transiently ({type(last_error).__name__}: {last_error})") from last_error
        if decoded is None:
            raise ProviderPermanentError("AIHubMix returned no response")
        if not isinstance(decoded, Mapping):
            raise ProviderPermanentError("AIHubMix returned a non-object response")
        return decoded


def _curl_json(base_url: str, method: str, path: str, body: Mapping[str, Any], api_key: str, request_timeout: float) -> Mapping[str, Any] | None:
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        return None
    handle, temporary_headers = tempfile.mkstemp(prefix="ioabench-headers-", suffix=".txt")
    os.close(handle)
    command = [executable, "--http1.1", "--silent", "--show-error", "--max-time", f"{max(0.01, request_timeout):.3f}", "--request", method, _request_url(base_url, path), "--header", f"Authorization: Bearer {api_key}", "--header", "Content-Type: application/json", "--dump-header", temporary_headers, "--write-out", "\\n__IOA_STATUS__%{http_code}"]
    temporary_body: str | None = None
    if method == "POST":
        encoded_body = json.dumps(body)
        if len(encoded_body) > 6000:
            handle, temporary_body = tempfile.mkstemp(prefix="ioabench-", suffix=".json")
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(encoded_body)
            command.extend(["--data-binary", f"@{temporary_body}"])
        else:
            command.extend(["--data", encoded_body])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False,
                                   timeout=request_timeout + 1)
        with open(temporary_headers, encoding="utf-8", errors="replace") as stream:
            # Redirects/proxy handshakes may precede the final response header block.
            blocks = re.split(r"\r?\n\r?\n", stream.read().strip())
            header_lines = blocks[-1].splitlines()
            headers = dict(line.split(":", 1) for line in header_lines if ":" in line)
        transport_metadata = _response_headers(headers)
    except subprocess.TimeoutExpired:
        # TimeoutExpired includes the credential-bearing command in its repr.
        raise ProviderTransientError("AIHubMix curl exceeded its remaining request deadline "
                                     "(curl_returncode=unavailable, http_status=unknown)") from None
    finally:
        os.unlink(temporary_headers)
        if temporary_body:
            try:
                os.unlink(temporary_body)
            except OSError:
                pass
    marker = "\n__IOA_STATUS__"
    if marker not in completed.stdout:
        return None
    raw, status_text = completed.stdout.rsplit(marker, 1)
    try:
        status = int(status_text.strip())
    except ValueError:
        return None
    diagnostic_headers = {name: (value.replace(api_key, "[REDACTED]") if api_key else value)[:240]
                          for name, value in transport_metadata.items()
                          if name in {"x-request-id", "retry-after", "x-aihubmix-model"}}
    diagnostic_fields = {"curl_returncode": completed.returncode, "http_status": f"{status:03d}",
                         "response_characters": len(raw), "headers": diagnostic_headers}
    if status >= 400:
        try:
            error_payload = json.loads(raw)
        except json.JSONDecodeError:
            error_payload = None
        if isinstance(error_payload, Mapping):
            error_fields = {"tid": error_payload.get("tid")}
            if isinstance(error_payload.get("error"), Mapping):
                error_fields.update({f"error.{name}": error_payload["error"].get(name)
                                     for name in ("type", "code", "tid")})
            diagnostic_fields.update({name: (value.replace(api_key, "[REDACTED]") if api_key else value)[:240]
                                      for name, value in error_fields.items() if isinstance(value, str)})
    diagnostic = json.dumps(diagnostic_fields, sort_keys=True)
    if status == 404:
        raise ModelUnsupportedError(f"AIHubMix endpoint or model is unavailable; {diagnostic}")
    if status == 429 or status >= 500:
        raise ProviderTransientError(f"AIHubMix transient HTTP {status}; {diagnostic}")
    if status >= 400:
        raise ProviderPermanentError(f"AIHubMix HTTP {status}; {diagnostic}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        kind = "empty" if not raw.strip() else "non-JSON"
        raise ProviderTransientError(f"AIHubMix curl response was {kind}; {diagnostic}") from exc
    if not isinstance(payload, Mapping):
        raise ProviderPermanentError("AIHubMix returned a non-object response")
    payload["transport_metadata"] = transport_metadata
    return payload


def _response_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    allowed = {"x-aihubmix-model", "x-aihubmix-fallback", "x-structured-output-degraded",
               "x-request-id", "retry-after"}
    return {str(key).lower(): str(value).strip() for key, value in headers.items()
            if str(key).lower() in allowed}


def _model_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    items = payload.get("data", ())
    if not isinstance(items, list):
        raise ProviderPermanentError("AIHubMix model catalog has invalid data")
    return tuple(item for item in items if isinstance(item, Mapping))


def _request_url(base_url: str, path: str) -> str:
    if path.startswith(("/api/", "/model-data/")) and base_url.endswith("/v1"):
        return f"{base_url[:-3]}{path}"
    return f"{base_url}{path}"


def _response_from_payload(payload: Mapping[str, Any], model_id: str) -> ModelResponse:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderPermanentError("AIHubMix response has no choices")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ProviderPermanentError("AIHubMix response choice is invalid")
    message = choice.get("message") or {}
    if not isinstance(message, Mapping):
        raise ProviderPermanentError("AIHubMix response message is invalid")
    tool_calls = message.get("tool_calls") or ()
    # The served identity (payload["model"], e.g. a dated snapshot id) and the
    # response id must stay in provider_metadata so a run can never be scored
    # under the requested name when the gateway actually served another model.
    metadata = {key: value for key, value in payload.items() if key not in {"choices", "usage"}}
    metadata["endpoint_family"] = "openai-chat-completions"
    reasoning_content = message.get("reasoning_content")
    reasoning_details = message.get("reasoning_details")
    return ModelResponse(
        text=message.get("content") if isinstance(message.get("content"), str) else None,
        tool_calls=tuple(tool_calls) if isinstance(tool_calls, list) else (),
        usage=dict(payload.get("usage") or {}),
        provider_metadata=metadata,
        model_id=model_id,
        finish_reason=choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None,
        reasoning_content=reasoning_content if isinstance(reasoning_content, str) else None,
        reasoning_details=reasoning_details if isinstance(reasoning_details, (Mapping, list)) else None,
    )
