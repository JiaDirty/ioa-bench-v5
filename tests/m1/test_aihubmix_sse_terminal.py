import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ioabench.errors import ProviderPermanentError, ProviderTransientError
from ioabench.models.aihubmix import AIHubMixAdapter


@pytest.mark.parametrize("defect", [None, "done", "finish", "usage", "model", "malformed", "401", "403"])
def test_sse_requires_observed_terminal_identity_usage_and_valid_chunks(monkeypatch, defect):
    def curl(command, **kwargs):
        header = Path(command[command.index("--dump-header") + 1])
        output = Path(command[command.index("--output") + 1])
        status = defect if defect in {"401", "403"} else "200"
        header.write_text(f"HTTP/1.1 {status} response\n\n", encoding="utf-8")
        chunk = {"model": "deepseek-v4.1-flash-1017", "id": "test",
                 "choices": [{"index": 0, "finish_reason": "stop", "delta": {"content": "{}"}}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": 2}}
        if defect == "finish":
            chunk["choices"][0]["finish_reason"] = None
        if defect in {"model", "usage"}:
            chunk.pop(defect)
        data = "data: " + json.dumps(chunk) + "\n\n"
        if defect == "malformed":
            data += 'data: {broken\n\n'
        if defect != "done":
            data += "data: [DONE]\n\n"
        output.write_text(data, encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("ioabench.models.aihubmix.subprocess.run", curl)
    monkeypatch.setattr("ioabench.models.aihubmix.shutil.which", lambda name: "curl")
    port = AIHubMixAdapter(api_key="test-key", stop_on_provider_error=True)
    if defect:
        error = ProviderPermanentError if defect in {"401", "403"} else ProviderTransientError
        with pytest.raises(error):
            port._request_sse("/chat/completions", {})
    else:
        result = port._request_sse("/chat/completions", {})
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["transport_metadata"]["sse_terminal_complete"] is True


def test_orphan_study_intent_is_never_sent_again(tmp_path):
    import asyncio
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation.aihubmix_study import AihubmixStudy, BASE_URL, MODEL, parameters
    from ioabench.v5.ai_generation.auxiliary_runtime import RequestUnresolved

    study = AihubmixStudy(tmp_path, SimpleNamespace(base_url=BASE_URL), [{"id": MODEL}])
    messages, params = [{"role": "user", "content": "{}"}], parameters()
    study.ledger("REQUEST_INTENT", request_id="orphan", directory="model_io", parameters=params,
                 messages_sha256=canonical_sha256(messages), tools_sha256=canonical_sha256([]))
    before = (tmp_path / "REQUEST_LEDGER.jsonl").read_bytes()
    with pytest.raises(RequestUnresolved):
        asyncio.run(study.invoke(tmp_path / "model_io", "orphan", messages, params))
    assert (tmp_path / "REQUEST_LEDGER.jsonl").read_bytes() == before
