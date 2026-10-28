import asyncio

import pytest

from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.models.aihubmix import _native_request, _native_response


def test_explicit_auxiliary_responses_roundtrip_retains_reasoning_items_and_usage():
    requests = []
    def requester(method, path, body):
        requests.append((method, path, body))
        return {"id": "r1", "model": "sol-revision", "status": "completed", "output": [
            {"type": "reasoning", "id": "reasoning1", "summary": []},
            {"type": "function_call", "id": "fc1", "call_id": "call1", "name": "echo", "arguments": '{"value":42}'}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 2}}}
    port = AIHubMixAdapter(requester=requester)
    profile = ModelProfile("aihubmix", "sol", {"endpoint_family": "openai.responses"}, {}, "AUX_PROTOCOL_PROBE")
    response = asyncio.run(port.generate(profile, ModelRequest([{"role": "user", "content": "echo"}], {"max_output_tokens": 16384})))
    assert requests[0][1] == "/responses" and requests[0][2]["input"] == [{"role": "user", "content": "echo"}]
    assert response.finish_reason == "tool_calls" and response.tool_calls[0]["id"] == "call1"
    assert response.usage["total_tokens"] == 15 and response.usage["output_tokens_details"]["reasoning_tokens"] == 2
    followup = ModelRequest([{"role": "assistant", "content": "", "output_items": response.provider_metadata["output_items"]},
                            {"role": "tool", "tool_call_id": "call1", "content": "42"}], {})
    items = _native_request("sol", followup, "openai.responses")["input"]
    assert items[0]["id"] == "reasoning1" and items[-1] == {"type": "function_call_output", "call_id": "call1", "output": "42"}


def test_anthropic_signed_thinking_and_multiple_tool_results_survive_translation():
    blocks = [{"type": "thinking", "thinking": "check", "signature": "signed"},
              {"type": "tool_use", "id": "t1", "name": "echo", "input": {"value": 42}}]
    reply = _native_response({"model": "haiku", "content": blocks, "stop_reason": "tool_use",
        "usage": {"input_tokens": 20, "output_tokens": 8, "cache_read_input_tokens": 4}}, "haiku", "anthropic.messages")
    body = _native_request("haiku", ModelRequest([
        {"role": "system", "content": "neutral"}, {"role": "assistant", "content": "", "content_blocks": reply.provider_metadata["content_blocks"]},
        {"role": "tool", "tool_call_id": "t1", "content": "42"},
        {"role": "tool", "tool_call_id": "t2", "content": "43"}], {"max_tokens": 16384}), "anthropic.messages")
    assert body["system"] == "neutral"
    assert body["messages"][0]["content"][0]["signature"] == "signed"
    assert len(body["messages"][1]["content"]) == 2
    assert reply.finish_reason == "tool_calls" and reply.usage["cache_read_input_tokens"] == 4
    assert reply.usage["prompt_tokens"] == 24 and reply.usage["total_tokens"] == 32


@pytest.mark.parametrize(("protocol", "payload"), [
    ("openai.responses", {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []}),
    ("anthropic.messages", {"stop_reason": "max_tokens", "content": []})])
def test_native_length_is_never_normal_completion(protocol, payload):
    assert _native_response(payload, "candidate", protocol).finish_reason == "length"


def test_formal_default_chat_wire_body_remains_unchanged():
    calls = []
    def requester(method, path, body):
        calls.append((path, body))
        return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    profile = ModelProfile("aihubmix", "frozen", {}, {})
    asyncio.run(AIHubMixAdapter(requester=requester).generate(profile,
        ModelRequest([{"role": "user", "content": "hello"}], {"max_tokens": 131072})))
    assert calls == [("/chat/completions", {"model": "frozen", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 131072})]
