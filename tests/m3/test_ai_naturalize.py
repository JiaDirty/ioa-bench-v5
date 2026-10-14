import asyncio
import json

from ioabench.generation.ai_naturalize import naturalize_candidates
from ioabench.errors import ProviderTransientError
from ioabench.models import ModelProfile, ModelResponse
from ioabench.suites.t321.generation import T321Generator


class StubAdapter:
    async def resolve(self, model_id: str) -> ModelProfile:
        return ModelProfile("aihubmix", model_id, {}, {})

    async def generate(self, profile: ModelProfile, request) -> ModelResponse:
        payload = json.loads(request.messages[-1]["content"])
        return ModelResponse(json.dumps({"results": [{"candidate_id": item["candidate_id"], "context": "A neutral local task context.", "message": "A neutral local task message."} for item in payload["cases"]]}), model_id=profile.model_id)


class FlakyAdapter(StubAdapter):
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, profile: ModelProfile, request) -> ModelResponse:
        self.calls += 1
        if self.calls < 5:
            raise ProviderTransientError("temporary provider failure")
        return await super().generate(profile, request)


def test_generic_naturalization_caches_visible_text_without_oracle(tmp_path) -> None:
    skeletons = [T321Generator().generate(seed=index, condition="RISK") for index in (1, 2)]
    cache = tmp_path / "naturalization.json"
    result, failures = asyncio.run(naturalize_candidates(skeletons, model_id="generator", cache_path=cache, adapter=StubAdapter()))
    assert not failures
    assert set(result) == {item.candidate_id for item in skeletons}
    assert result[skeletons[0].candidate_id].visible()["naturalized_context"]
    assert "oracle" not in cache.read_text(encoding="utf-8").casefold()


def test_generic_naturalization_retries_transient_provider_failures(tmp_path, monkeypatch) -> None:
    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("ioabench.generation.ai_naturalize.asyncio.sleep", no_sleep)
    adapter = FlakyAdapter()
    skeleton = T321Generator().generate(seed=1, condition="RISK")
    result, failures = asyncio.run(naturalize_candidates([skeleton], model_id="generator", cache_path=tmp_path / "naturalization.json", adapter=adapter))
    assert not failures
    assert set(result) == {skeleton.candidate_id}
    assert adapter.calls == 5
