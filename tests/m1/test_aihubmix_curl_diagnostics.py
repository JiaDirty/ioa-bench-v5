"""Curl failure evidence is useful without echoing credentials or provider bodies."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from ioabench.errors import ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
import ioabench.models.aihubmix as module


SECRET = "private-api-key-fixture"


def _curl_stub(monkeypatch, *, raw="", status="200", returncode=0):
    paths = []

    def run(command, **kwargs):
        assert kwargs["check"] is False and kwargs["capture_output"] is True
        assert command[command.index("--max-time") + 1] == "2.000"
        headers = Path(command[command.index("--dump-header") + 1])
        paths.append(headers)
        headers.write_text(
            "HTTP/1.1 200 Connection established\nX-Request-Id: proxy-handshake\n\n"
            f"HTTP/1.1 {status} Final\nX-Request-Id: request-42\nRetry-After: 60\n"
            f"X-Aihubmix-Model: audit-model\nSet-Cookie: {SECRET}\nAuthorization: Bearer {SECRET}\n\n",
            encoding="utf-8")
        return SimpleNamespace(stdout=raw + "\n__IOA_STATUS__" + status,
                               stderr=f"stderr command Authorization: Bearer {SECRET}", returncode=returncode)

    monkeypatch.setattr(module.shutil, "which", lambda _: "curl.exe")
    monkeypatch.setattr(module.subprocess, "run", run)
    return paths


def _call():
    return module._curl_json("https://aihubmix.com/v1", "POST", "/chat/completions", {}, SECRET, 2)


@pytest.mark.parametrize("returncode,status", [(0, "200"), (28, "000")])
def test_empty_response_distinguishes_received_http_from_curl_timeout(monkeypatch, returncode, status):
    paths = _curl_stub(monkeypatch, returncode=returncode, status=status)
    with pytest.raises(ProviderTransientError) as error:
        _call()
    message = str(error.value)
    assert "response was empty" in message
    diagnostic = json.loads(message.split("; ", 1)[1])
    assert diagnostic["curl_returncode"] == returncode
    assert diagnostic["http_status"] == status
    assert diagnostic["response_characters"] == 0
    assert diagnostic["headers"] == {"x-request-id": "request-42", "retry-after": "60",
                                     "x-aihubmix-model": "audit-model"}
    assert SECRET not in message and "Authorization" not in message and "stderr" not in message
    assert "proxy-handshake" not in message
    assert all(not path.exists() for path in paths)


def test_non_json_body_and_stderr_never_appear_in_error(monkeypatch):
    paths = _curl_stub(monkeypatch, raw=f"Provider echoed Authorization: Bearer {SECRET}")
    with pytest.raises(ProviderTransientError) as error:
        _call()
    message = str(error.value)
    assert "response was non-JSON" in message
    assert json.loads(message.split("; ", 1)[1])["response_characters"] > 0
    assert SECRET not in message and "Authorization" not in message and "stderr" not in message
    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize("status,exception", [("404", ModelUnsupportedError),
    ("429", ProviderTransientError), ("503", ProviderTransientError), ("401", ProviderPermanentError)])
def test_http_error_classification_is_unchanged_and_body_is_not_logged(monkeypatch, status, exception):
    _curl_stub(monkeypatch, raw=f"error body contains {SECRET}", status=status)
    with pytest.raises(exception) as error:
        _call()
    message = str(error.value)
    assert json.loads(message.split("; ", 1)[1])["http_status"] == status
    assert SECRET not in message and "error body contains" not in message


def test_allowed_header_value_redacts_reflected_api_key(monkeypatch):
    _curl_stub(monkeypatch)
    original = module._response_headers
    monkeypatch.setattr(module, "_response_headers", lambda headers: {
        **original(headers), "x-request-id": f"request-{SECRET}"})
    with pytest.raises(ProviderTransientError) as error:
        _call()
    assert SECRET not in str(error.value)
    assert "request-[REDACTED]" in str(error.value)


def test_subprocess_timeout_suppresses_credential_bearing_command_cause(monkeypatch):
    paths = []

    def run(command, **kwargs):
        paths.append(Path(command[command.index("--dump-header") + 1]))
        raise subprocess.TimeoutExpired(command, 3, output=SECRET, stderr=SECRET)

    monkeypatch.setattr(module.shutil, "which", lambda _: "curl.exe")
    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(ProviderTransientError) as error:
        _call()
    assert "remaining request deadline" in str(error.value)
    assert SECRET not in str(error.value)
    assert error.value.__suppress_context__
    assert error.value.__cause__ is None
    assert all(not path.exists() for path in paths)


def test_http_401_keeps_only_structured_error_code_type_and_trace_ids(monkeypatch):
    hidden = "other-secret-not-allowed"
    raw = json.dumps({"error": {"type": "authentication_error", "code": "invalid_api_key",
                               "tid": "nested-trace-42", "message": hidden,
                               "authorization": SECRET, "details": {"secret": hidden}},
                      "tid": "outer-trace-42", "message": hidden, "api_key": SECRET, "token": hidden})
    _curl_stub(monkeypatch, raw=raw, status="401")
    with pytest.raises(ProviderPermanentError) as error:
        _call()
    message = str(error.value)
    diagnostic = json.loads(message.split("; ", 1)[1])
    assert {key: diagnostic[key] for key in ("error.type", "error.code", "error.tid", "tid")} == {
        "error.type": "authentication_error", "error.code": "invalid_api_key",
        "error.tid": "nested-trace-42", "tid": "outer-trace-42"}
    assert set(diagnostic) == {"curl_returncode", "http_status", "response_characters", "headers",
                               "error.type", "error.code", "error.tid", "tid"}
    assert SECRET not in message and hidden not in message
    assert "authorization" not in message.casefold() and "details" not in message


def test_structured_error_values_are_redacted_and_bounded(monkeypatch):
    raw = json.dumps({"error": {"type": SECRET, "code": "trace-" + SECRET,
                               "tid": "x" * 500}, "tid": SECRET})
    _curl_stub(monkeypatch, raw=raw, status="401")
    with pytest.raises(ProviderPermanentError) as error:
        _call()
    diagnostic = json.loads(str(error.value).split("; ", 1)[1])
    assert diagnostic["error.type"] == diagnostic["tid"] == "[REDACTED]"
    assert diagnostic["error.code"] == "trace-[REDACTED]"
    assert diagnostic["error.tid"] == "x" * 240
    assert SECRET not in str(error.value)


def test_structured_error_whitelist_ignores_non_string_containers(monkeypatch):
    raw = json.dumps({"error": {"type": {"secret": SECRET}, "code": [SECRET], "tid": 17},
                      "tid": {"secret": SECRET}})
    _curl_stub(monkeypatch, raw=raw, status="401")
    with pytest.raises(ProviderPermanentError) as error:
        _call()
    diagnostic = json.loads(str(error.value).split("; ", 1)[1])
    assert set(diagnostic) == {"curl_returncode", "http_status", "response_characters", "headers"}
    assert SECRET not in str(error.value)
