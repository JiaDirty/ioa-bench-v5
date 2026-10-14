import asyncio

from ioabench.models import MockModel, ModelProfile, ModelRequest, ModelResponse


def test_mock_model_supports_scripted_text_and_tool_responses() -> None:
    model = MockModel([
        ModelResponse(text="hello"),
        ModelResponse(text=None, tool_calls=({"name": "sandbox.lookup"},)),
    ])
    profile = ModelProfile("mock", "mock", {}, {})
    request = ModelRequest(messages=({"role": "user", "content": "x"},), parameters={})

    first = asyncio.run(model.generate(profile, request))
    second = asyncio.run(model.generate(profile, request))
    assert first.text == "hello"
    assert second.tool_calls[0]["name"] == "sandbox.lookup"
