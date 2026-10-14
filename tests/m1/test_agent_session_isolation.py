import asyncio

from ioabench.agents import AgentSessionManager, AgentSpec
from ioabench.models import ModelProfile, ModelResponse


class FakeModel:
    async def resolve(self, model_id):
        return ModelProfile("aihubmix", model_id, {}, {})

    async def generate(self, profile, request):
        return ModelResponse(text=f"reply:{request.role_metadata['agent_id']}", model_id=profile.model_id)


def test_same_model_sessions_keep_context_memory_and_prompts_separate() -> None:
    profile = ModelProfile("aihubmix", "model", {}, {})
    manager = AgentSessionManager(FakeModel(), profile)
    first = manager.create(AgentSpec("a1", "org-a", "coordinator", "private-a"))
    second = manager.create(AgentSpec("a2", "org-b", "analyst", "private-b"))

    asyncio.run(first.generate("first"))
    second.memory["only_second"] = True
    manager.send_message("a1", "a2", "explicit peer content")

    assert first.spec.system_prompt == "private-a"
    assert second.spec.system_prompt == "private-b"
    assert "explicit peer content" not in [item["content"] for item in first.messages if "content" in item]
    assert second.memory == {"only_second": True}
    assert first.memory == {}
