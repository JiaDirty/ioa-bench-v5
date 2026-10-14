import asyncio
import json

from ioabench.errors import ProviderTransientError
from ioabench.generation.ai_semantic import validate_candidates
from ioabench.generation.ai_semantic import _batch_prompt
from ioabench.models import ModelProfile, ModelResponse


class StubAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self.fail_secondary = True
        self.payloads = []

    async def resolve(self, model_id: str) -> ModelProfile:
        return ModelProfile("aihubmix", model_id, {}, {})

    async def generate(self, profile: ModelProfile, request) -> ModelResponse:
        self.calls += 1
        if self.fail_secondary and profile.model_id == "secondary":
            raise ProviderTransientError("temporary")
        payload = json.loads(request.messages[-1]["content"])
        self.payloads.append(payload)
        if "cases" in payload:
            text = json.dumps({"results": [{"candidate_id": item["candidate_id"], "label": "ACCEPT", "confidence": 0.9, "evidence_refs": ["task"]} for item in payload["cases"]]})
        else:
            text = json.dumps({"label": "ACCEPT", "confidence": 0.9, "evidence_refs": ["task"]})
        return ModelResponse(text, model_id=profile.model_id)


def test_transient_validation_is_retried_and_cache_is_model_scoped(tmp_path) -> None:
    adapter = StubAdapter()
    records = [{"candidate_id": "case-1", "sut_payload": {"task": "approve an invoice"}}]
    cache = tmp_path / "semantic.json"
    options = {"adapter": adapter, "primary_model": "primary", "secondary_model": "secondary", "cache_path": cache}

    first = asyncio.run(validate_candidates(records, **options))
    assert not first[0].accepted
    assert json.loads(cache.read_text(encoding="utf-8"))["results"] == []

    adapter.fail_secondary = False
    second = asyncio.run(validate_candidates(records, **options))
    assert second[0].accepted
    previous_calls = adapter.calls
    assert asyncio.run(validate_candidates(records, **options)) == second
    assert adapter.calls == previous_calls

    asyncio.run(validate_candidates(records, **{**options, "secondary_model": "other-validator"}))
    assert adapter.calls > previous_calls


def test_semantic_validation_uses_opaque_ids_for_condition_labeled_cases(tmp_path) -> None:
    adapter = StubAdapter()
    adapter.fail_secondary = False
    records = [{"candidate_id": "T321-1-0-risk", "sut_payload": {"task": "review"}}]
    asyncio.run(validate_candidates(records, adapter=adapter, primary_model="primary", secondary_model="secondary", cache_path=tmp_path / "semantic.json"))
    ids = [item["candidate_id"] for payload in adapter.payloads for item in payload.get("cases", [payload])]
    assert ids and all("risk" not in item.casefold() and "control" not in item.casefold() for item in ids)


def test_semantic_prompt_allows_intended_visible_conflicts() -> None:
    system = _batch_prompt("coherence", [{"candidate_id": "case-1", "sut_payload": {}}])[0]["content"]
    assert "may intentionally contain conflicting claims or evidence" in system
