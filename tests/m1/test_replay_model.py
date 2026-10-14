import asyncio

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile, ModelRequest, ModelResponse, ReplayModel


def test_replay_model_reproduces_response_for_normalized_request() -> None:
    request = ModelRequest(messages=({"role": "user", "content": "x"},), parameters={"temperature": 0})
    key = canonical_sha256({"messages": list(request.messages), "parameters": dict(request.parameters), "tools": list(request.tools)})
    model = ReplayModel({key: ModelResponse(text="recorded", model_id="model")})

    response = asyncio.run(model.generate(ModelProfile("replay", "model", {}, {}), request))
    assert response.text == "recorded"


def test_replay_model_rejects_missing_request() -> None:
    model = ReplayModel({})
    with pytest.raises(KeyError, match="no replay response"):
        asyncio.run(model.generate(ModelProfile("replay", "model", {}, {}), ModelRequest(messages=({"role": "user", "content": "x"},), parameters={})))
