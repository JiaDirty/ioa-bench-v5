"""Retain interrupted stream evidence and use an already complete application response."""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models.aihubmix import AIHubMixAdapter
from ioabench.models.types import ModelProfile, ModelRequest
from ioabench.v5.ai_generation.auxiliary_runtime import classify_provider_failure

SECRET = "test-api-key-not-for-evidence"


def stream_call(monkeypatch, tmp_path, *, returncode, defect=None, status=200):
    chunk = {"model": "test-model", "id": "test-response",
             "choices": [{"index": 0, "finish_reason": "stop", "delta": {"content": "{}"}}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 2}}
    if defect == "finish":
        chunk["choices"][0]["finish_reason"] = None
    if defect in {"usage", "model"}:
        chunk.pop(defect)
    data = "data: " + json.dumps(chunk) + "\n\n"
    if defect == "malformed":
        data += "data: {broken\n\n"
    if defect != "done":
        data += "data: [DONE]\n\n"
    headers = f"HTTP/1.1 {status} response\r\nContent-Type: text/event-stream\r\n\r\n"
    calls = []

    def curl(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        header = Path(command[command.index("--dump-header") + 1])
        body = Path(command[command.index("--data-binary") + 1][1:])
        request = json.loads(body.read_text(encoding="utf-8"))
        assert "stream_evidence_path" not in json.dumps(request)
        assert SECRET not in body.read_text(encoding="utf-8")
        output.write_bytes(data.encode("utf-8"))
        header.write_bytes(headers.encode("utf-8"))
        calls.append((output, header, body))
        return SimpleNamespace(returncode=returncode, stderr="curl: (56) schannel: server closed abruptly (missing close_notify)")

    monkeypatch.setattr("ioabench.models.aihubmix.subprocess.run", curl)
    monkeypatch.setattr("ioabench.models.aihubmix.shutil.which", lambda name: "curl")
    port = AIHubMixAdapter(api_key=SECRET, stop_on_provider_error=True)
    profile = ModelProfile("aihubmix", "test-model", {}, {})
    request = ModelRequest(({"role": "user", "content": "Return JSON."},), {"stream": True},
                           role_metadata={"stream_evidence_path": str(tmp_path / "attempt-001.sse")})
    return port, profile, request, calls, data, headers


def assert_retained_evidence(transport, calls, data, headers, tmp_path):
    assert len(calls) == 1
    assert not any(path.exists() for path in calls[0])
    evidence = transport["stream_evidence"]
    assert Path(evidence["sse_path"]) == tmp_path / "attempt-001.sse"
    assert Path(evidence["headers_path"]) == tmp_path / "attempt-001.headers"
    assert Path(evidence["sse_path"]).read_bytes() == data.encode("utf-8")
    assert Path(evidence["headers_path"]).read_bytes() == headers.encode("utf-8")
    assert evidence["sse_bytes"] == len(data.encode("utf-8"))
    assert evidence["sse_sha256"] == hashlib.sha256(data.encode("utf-8")).hexdigest()
    assert evidence["headers_sha256"] == hashlib.sha256(headers.encode("utf-8")).hexdigest()
    assert all(SECRET not in path.read_text(encoding="utf-8") for path in tmp_path.iterdir())


def test_complete_stream_with_curl56_is_parsed_once_and_keeps_transport_evidence(monkeypatch, tmp_path):
    port, profile, request, calls, data, headers = stream_call(monkeypatch, tmp_path, returncode=56)
    response = asyncio.run(port.generate(profile, request))
    assert response.text == "{}" and response.finish_reason == "stop"
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 2}
    transport = response.provider_metadata["transport_metadata"]
    assert transport["http_status"] == 200 and transport["curl_returncode"] == 56
    assert transport["sse_terminal_complete"] is True
    assert_retained_evidence(transport, calls, data, headers, tmp_path)


@pytest.mark.parametrize("defect", ["done", "finish", "usage", "model", "malformed"])
def test_incomplete_stream_with_curl56_stays_unknown_and_keeps_evidence(monkeypatch, tmp_path, defect):
    port, profile, request, calls, data, headers = stream_call(monkeypatch, tmp_path, returncode=56, defect=defect)
    with pytest.raises(ProviderTransientError) as caught:
        asyncio.run(port.generate(profile, request))
    assert classify_provider_failure(caught.value) == "REQUEST_UNRESOLVED"
    transport = caught.value.transport_metadata
    assert transport["http_status"] == 200 and transport["curl_returncode"] == 56
    assert "sse_terminal_complete" not in transport
    assert_retained_evidence(transport, calls, data, headers, tmp_path)


@pytest.mark.parametrize("status,error,category", [
    (401, ProviderPermanentError, "AUTH/PERMISSION"),
    (500, ProviderTransientError, "NETWORK_TRANSIENT"),
])
def test_http_error_is_not_accepted_even_with_complete_stream(monkeypatch, tmp_path, status, error, category):
    port, profile, request, calls, data, headers = stream_call(monkeypatch, tmp_path, returncode=56, status=status)
    with pytest.raises(error) as caught:
        asyncio.run(port.generate(profile, request))
    assert classify_provider_failure(caught.value) == category
    transport = caught.value.transport_metadata
    assert transport["http_status"] == status and transport["curl_returncode"] == 56
    assert_retained_evidence(transport, calls, data, headers, tmp_path)


def test_normal_success_cleans_temp_stream_without_duplicate_permanent_copy(monkeypatch, tmp_path):
    port, profile, request, calls, _, _ = stream_call(monkeypatch, tmp_path, returncode=0)
    response = asyncio.run(port.generate(profile, request))
    assert response.provider_metadata["transport_metadata"]["curl_returncode"] == 0
    assert "stream_evidence" not in response.provider_metadata["transport_metadata"]
    assert len(calls) == 1 and not any(path.exists() for path in calls[0])
    assert not list(tmp_path.iterdir())
