import asyncio

import pytest

from ioabench.models import ModelProfile, ModelRequest, ModelResponse, normalize_request


def test_request_and_response_capture_provider_neutral_metadata() -> None:
    profile = ModelProfile(
        provider="aihubmix", model_id="deepseek-v4.1-flash",
        capabilities={"tools": True}, default_parameters={"temperature": 0},
    )
    request = normalize_request(ModelRequest(
        messages=({"role": "user", "content": "hello"},),
        parameters={"temperature": 0},
        tools=({"name": "sandbox.lookup"},),
        role_metadata={"model_role": "TESTED", "agent_id": "agent-1"},
    ))
    response = ModelResponse(
        text="ok", usage={"input_tokens": 1, "output_tokens": 1},
        provider_metadata={"request_id": "req-1"}, model_id=profile.model_id,
        finish_reason="stop",
    )

    assert request.role_metadata["model_role"] == "TESTED"
    assert request.tools[0]["name"] == "sandbox.lookup"
    assert response.model_id == profile.model_id
    assert response.finish_reason == "stop"


def test_invalid_request_is_rejected_before_provider_call() -> None:
    with pytest.raises(ValueError, match="at least one message"):
        normalize_request(ModelRequest(messages=(), parameters={}))
    with pytest.raises(ValueError, match="role and content"):
        normalize_request(ModelRequest(messages=({"role": "user"},), parameters={}))
