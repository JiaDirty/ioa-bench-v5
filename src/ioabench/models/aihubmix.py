from __future__ import annotations
import asyncio
from collections.abc import Callable, Mapping
import hashlib
import json
import os
from pathlib import Path
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
DEFAULT_BASE_URL = "https://api.inferera.com/v1"


class AIHubMixAdapter:
    def __init__(self, *, api_key: str | None = None, base_url: str = DEFAULT_BASE_URL, fallback_base_url: str = DEFAULT_BASE_URL, requester: JsonRequester | None = None, request_timeout: float = 900.0, stop_on_provider_error: bool = False) -> None:
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
        endpoint = getattr(profile, "capabilities", {}).get("endpoint_family", "openai.chat_completions")
        if endpoint in {"openai.responses", "anthropic.messages"}:
            body = _native_request(profile.model_id, request, endpoint)
            path = "/responses" if endpoint == "openai.responses" else "/messages"
            payload = await asyncio.to_thread(self._requester, "POST", path, body)
            return _native_response(payload, profile.model_id, endpoint)
        if endpoint != "openai.chat_completions":
            raise ModelUnsupportedError("unsupported AIHubMix endpoint family")
        body: dict[str, Any] = {"model": profile.model_id, "messages": list(request.messages), **dict(request.parameters)}
        if request.tools:
            body["tools"] = list(request.tools)
        if body.get("stream") and not request.tools:
            # streaming keeps the connection alive through long thinking turns that
            # the gateway otherwise cuts at ~80-100s on non-streaming requests; the
            # SSE stream is aggregated into the exact non-streaming response shape
            body = {**body, "stream": True, "stream_options": {"include_usage": True}}
            payload = await asyncio.to_thread(self._request_sse, "/chat/completions", body,
                                             evidence_path=request.role_metadata.get("stream_evidence_path"))
            return _response_from_payload(payload, profile.model_id)
        payload = await asyncio.to_thread(self._requester, "POST", "/chat/completions", body)
        return _response_from_payload(payload, profile.model_id)

    def _request_sse(self, path: str, body: Mapping[str, Any], *,
                     evidence_path: str | None = None) -> Mapping[str, Any]:
        """POST with SSE streaming and aggregate chunks into one response object."""
        if not self._api_key:
            raise ConfigurationError("AIHUBMIX_API_KEY is required for provider calls")
        base_url = self.base_url if self.stop_on_provider_error else self.base_url
        executable = shutil.which("curl.exe") or shutil.which("curl")
        if executable is None:
            raise ProviderPermanentError("streaming transport requires curl")
        handle, sse_path = tempfile.mkstemp(prefix="ioabench-sse-", suffix=".txt")
        os.close(handle)
        handle, headers_path = tempfile.mkstemp(prefix="ioabench-headers-", suffix=".txt")
        os.close(handle)
        handle, body_path = tempfile.mkstemp(prefix="ioabench-", suffix=".json")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(body))
        retain_stream = False
        curl_returncode = None
        transport: dict[str, Any] = {}
        try:
            command = [executable, "--http1.1", "--silent", "--show-error", "--no-buffer", "-N",
                       "--max-time", f"{self._request_timeout:.3f}", "--request", "POST",
                       _request_url(base_url, path),
                       "--header", f"Authorization: Bearer {self._api_key}",
                       "--header", "Content-Type: application/json",
                       "--header", "Accept: text/event-stream",
                       "--data-binary", f"@{body_path}",
                       "--dump-header", headers_path,
                       "--output", sse_path]
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=self._request_timeout + 30)
            curl_returncode = completed.returncode
            transport = _response_headers_from_file(headers_path)
            status = transport.get("http_status")
            if status and status >= 400:
                error_type = ProviderTransientError if status == 429 or status >= 500 else ProviderPermanentError
                raise error_type(f"AIHubMix streaming HTTP {status}")
            retain_stream = completed.returncode != 0
            if retain_stream and status != 200:
                raise ProviderTransientError(
                    f"AIHubMix streaming curl failed (returncode {completed.returncode}): "
                    f"{completed.stderr.strip()[:200]}")
            chunks: list[Mapping[str, Any]] = []
            done = False
            with open(sse_path, encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        done = True
                        continue
                    try:
                        value = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ProviderTransientError("AIHubMix streaming malformed JSON chunk; terminal unknown") from exc
                    if isinstance(value, Mapping):
                        chunks.append(value)
            if not chunks or not done:
                raise ProviderTransientError("AIHubMix streaming incomplete: missing data or DONE; terminal unknown")
            payload = _aggregate_sse(chunks, headers_path)
            transport = payload["transport_metadata"]
            transport["curl_returncode"] = curl_returncode
            return payload
        except (ProviderPermanentError, ProviderTransientError, subprocess.TimeoutExpired) as exc:
            # HTTP 200 headers do not resolve an interrupted completion. Keep
            # that evidence without exposing TimeoutExpired's credential argv.
            error = (ProviderTransientError("AIHubMix streaming deadline exceeded; terminal unknown")
                     if isinstance(exc, subprocess.TimeoutExpired) else exc)
            retain_stream = True
            transport = _response_headers_from_file(headers_path)
            transport["curl_returncode"] = curl_returncode
            error.transport_metadata = transport
            if isinstance(error, ProviderTransientError) and transport.get("http_status", 0) < 400:
                error.category = "REQUEST_UNRESOLVED"
            raise error from None
        finally:
            try:
                if retain_stream:
                    if evidence_path is not None:
                        target = Path(evidence_path)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(sse_path, target)
                        shutil.move(headers_path, target.with_suffix(".headers"))
                        sse_path, headers_path = str(target), str(target.with_suffix(".headers"))
                    transport["stream_evidence"] = {
                        "sse_path": sse_path, "headers_path": headers_path,
                        "sse_bytes": Path(sse_path).stat().st_size,
                        "sse_sha256": hashlib.sha256(Path(sse_path).read_bytes()).hexdigest(),
                        "headers_sha256": hashlib.sha256(Path(headers_path).read_bytes()).hexdigest()}
            finally:
                for temporary in (body_path,) if retain_stream else (sse_path, headers_path, body_path):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass

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
            headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
            if path == "/messages":
                headers.update({"x-api-key": self._api_key, "anthropic-version": "2023-06-01"})
            request = Request(_request_url(base_url, path), data=data, method=method, headers=headers)
            try:
                with urlopen(request, timeout=remaining) as response:
                    decoded = json.loads(response.read().decode("utf-8"))
                    if isinstance(decoded, dict):
                        decoded["transport_metadata"] = _response_headers(response.headers)
                        decoded["transport_metadata"]["http_status"] = getattr(response, "status", None)
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


def _aggregate_sse(chunks: list[Mapping[str, Any]], headers_path: str) -> Mapping[str, Any]:
    """Fold OpenAI-compatible SSE chunks into one non-streaming response object."""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason = None
    usage = None
    model_id = None
    response_id = None
    created = None
    for chunk in chunks:
        model_id = chunk.get("model") or model_id
        response_id = chunk.get("id") or response_id
        created = chunk.get("created") or created
        if chunk.get("usage"):
            usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta") or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning_parts.append(delta["reasoning_content"])
    transport = _response_headers_from_file(headers_path)
    if not finish_reason or not model_id or not usage or any(
            type(usage.get(key)) is not int or usage[key] < 0
            for key in ("prompt_tokens", "completion_tokens")):
        raise ProviderTransientError("AIHubMix streaming incomplete: missing finish/model/usage; terminal unknown")
    transport["sse_terminal_complete"] = True
    return {"id": response_id, "object": "chat.completion", "created": created,
            "model": model_id, "streamed": True,
            "choices": [{"index": 0, "finish_reason": finish_reason,
                         "message": {"role": "assistant",
                                     "content": "".join(content_parts),
                                     **({"reasoning_content": "".join(reasoning_parts)}
                                        if reasoning_parts else {})}}],
            "usage": usage or {},
            "transport_metadata": transport}


def _response_headers_from_file(headers_path: str) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    try:
        with open(headers_path, encoding="utf-8", errors="replace") as stream:
            blocks = re.split(r"\r?\n\r?\n", stream.read().strip())
    except OSError:
        return headers
    lines = blocks[-1].splitlines() if blocks else []
    if lines and lines[0].split(" ")[0].isdigit() is False and " " in lines[0]:
        try:
            headers["http_status"] = int(lines[0].split(" ")[1])
        except (IndexError, ValueError):
            pass
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _curl_json(base_url: str, method: str, path: str, body: Mapping[str, Any], api_key: str, request_timeout: float) -> Mapping[str, Any] | None:
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        return None
    handle, temporary_headers = tempfile.mkstemp(prefix="ioabench-headers-", suffix=".txt")
    os.close(handle)
    command = [executable, "--http1.1", "--silent", "--show-error", "--max-time", f"{max(0.01, request_timeout):.3f}", "--request", method, _request_url(base_url, path), "--header", f"Authorization: Bearer {api_key}", "--header", "Content-Type: application/json", "--dump-header", temporary_headers, "--write-out", "\\n__IOA_STATUS__%{http_code}"]
    if path == "/messages":
        command.extend(["--header", f"x-api-key: {api_key}", "--header", "anthropic-version: 2023-06-01"])
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
                if status in {400, 422}:
                    error_fields["error.message"] = error_payload["error"].get("message")
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
        error = ProviderTransientError(f"AIHubMix curl response was {kind}; {diagnostic}")
        # Receiving headers does not establish the completion's terminal state.
        if method == "POST" and completed.returncode != 0:
            error.category = "REQUEST_UNRESOLVED"
        raise error from exc
    if not isinstance(payload, Mapping):
        raise ProviderPermanentError("AIHubMix returned a non-object response")
    payload["transport_metadata"] = transport_metadata
    payload["transport_metadata"]["http_status"] = status
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


def _native_request(model_id: str, request: ModelRequest, endpoint: str) -> dict[str, Any]:
    """Translate the same ModelPort messages; native modes are explicit auxiliary opt-ins."""
    body = {"model": model_id, **dict(request.parameters)}
    if endpoint == "openai.responses":
        items = []
        for message in request.messages:
            if message.get("output_items"):
                items.extend(message["output_items"])
            elif message["role"] == "tool":
                items.append({"type": "function_call_output", "call_id": message["tool_call_id"], "output": message["content"]})
            else:
                items.append({"role": message["role"], "content": message["content"]})
                for call in message.get("tool_calls", []):
                    items.append({"type": "function_call", "call_id": call["id"], **call["function"]})
        body["input"] = items
        if request.tools:
            body["tools"] = [{"type": "function", **tool["function"]} for tool in request.tools]
    else:
        messages, system = [], []
        for message in request.messages:
            if message["role"] in {"system", "developer"}:
                system.append(message["content"])
                continue
            if message["role"] == "tool":
                role = "user"
                content = [{"type": "tool_result", "tool_use_id": message["tool_call_id"], "content": message["content"]}]
            else:
                role = message["role"]
                content = list(message.get("content_blocks") or [])
                if not content:
                    if message["content"]:
                        content.append({"type": "text", "text": message["content"]})
                    for call in message.get("tool_calls", []):
                        args = call["function"]["arguments"]
                        content.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"],
                                        "input": json.loads(args) if isinstance(args, str) else args})
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"].extend(content)
            else:
                messages.append({"role": role, "content": content})
        body["messages"] = messages
        if system:
            body["system"] = "\n\n".join(system)
        if request.tools:
            body["tools"] = [{"name": tool["function"]["name"],
                "description": tool["function"].get("description", ""),
                "input_schema": tool["function"]["parameters"]} for tool in request.tools]
    return body


def _native_response(payload: Mapping[str, Any], model_id: str, endpoint: str) -> ModelResponse:
    usage, calls, text, reasoning = dict(payload.get("usage") or {}), [], [], []
    metadata = {key: value for key, value in payload.items() if key not in {"output", "content", "usage"}}
    metadata["endpoint_family"] = endpoint
    if endpoint == "openai.responses":
        items = payload.get("output")
        if not isinstance(items, list):
            raise ProviderPermanentError("RESPONSE_PARSE: native response output must be an array")
        metadata["output_items"] = items
        for item in items:
            if item.get("type") == "function_call":
                calls.append({"id": item["call_id"], "type": "function", "function": {
                    "name": item["name"], "arguments": item["arguments"]}})
            if item.get("type") == "message":
                text.extend(block["text"] for block in item.get("content", []) if block.get("type") == "output_text")
            if item.get("type") == "reasoning":
                reasoning.extend(block.get("text", "") for block in item.get("summary", []))
        finish = "tool_calls" if calls else "stop"
        if payload.get("status") == "incomplete":
            finish = "length" if (payload.get("incomplete_details") or {}).get("reason") == "max_output_tokens" else "incomplete"
        elif payload.get("status") != "completed":
            finish = str(payload.get("status") or "unknown")
    else:
        items = payload.get("content")
        if not isinstance(items, list):
            raise ProviderPermanentError("RESPONSE_PARSE: native message content must be an array")
        metadata["content_blocks"] = items
        for item in items:
            if item.get("type") == "tool_use":
                calls.append({"id": item["id"], "type": "function", "function": {
                    "name": item["name"], "arguments": json.dumps(item["input"])}})
            elif item.get("type") == "text":
                text.append(item["text"])
            elif item.get("type") == "thinking":
                reasoning.append(item.get("thinking", ""))
        stop = payload.get("stop_reason")
        finish = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "tool_calls", "max_tokens": "length"}.get(stop, stop)
    if "input_tokens" in usage:
        cached = int(usage.get("cache_read_input_tokens") or 0)
        created = int(usage.get("cache_creation_input_tokens") or 0)
        usage["prompt_tokens"] = int(usage["input_tokens"]) + cached + created
        if cached or created:
            usage["prompt_tokens_details"] = {**usage.get("prompt_tokens_details", {}),
                "cached_tokens": cached, "cache_creation_tokens": created}
    if "output_tokens" in usage:
        usage["completion_tokens"] = usage["output_tokens"]
    if "total_tokens" not in usage and "prompt_tokens" in usage and "completion_tokens" in usage:
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return ModelResponse("".join(text), tuple(calls), usage=usage, provider_metadata=metadata,
        model_id=model_id, finish_reason=finish, reasoning_content="".join(reasoning) or None)
