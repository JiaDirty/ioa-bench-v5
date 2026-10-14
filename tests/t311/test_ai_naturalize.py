import asyncio
import json

import pytest

from ioabench.generation.ai_naturalize import _parse, naturalize_t311_pairs
from ioabench.models import ModelProfile, ModelResponse
from ioabench.suites.t311.generation import T311Generator


class StubGenerator:
    def __init__(self) -> None:
        self.calls = 0
        self.inputs = []

    async def resolve(self, model_id: str) -> ModelProfile:
        return ModelProfile("aihubmix", model_id, {}, {})

    async def generate(self, profile: ModelProfile, request) -> ModelResponse:
        self.calls += 1
        facts = json.loads(request.messages[-1]["content"])
        self.inputs.append(facts)
        return ModelResponse(
            json.dumps({
                "agent_card_summary": f"{facts['agent_id']} of {facts['organization']} lists {facts['capability']} for local workflow work.",
                "business_context": f"To {facts['task']}, the team uses {facts['documents']} in its normal queue.",
            }),
            usage={"total_tokens": 42}, model_id=profile.model_id,
        )


def test_t311_ai_naturalization_reuses_one_truth_free_input_for_a_pair(tmp_path) -> None:
    generator = T311Generator()
    pair = [generator.generate(seed=1, condition=condition) for condition in ("CONTROL", "RISK")]
    adapter = StubGenerator()
    options = {"model_id": "glm-5.2", "cache_path": tmp_path / "naturalization.json", "adapter": adapter}

    first, rejected = asyncio.run(naturalize_t311_pairs(pair, **options))
    second, _ = asyncio.run(naturalize_t311_pairs(pair, **options))

    assert not rejected
    assert first == second
    assert adapter.calls == 1
    assert len(first) == 1
    assert not any("oracle" in str(value).lower() or "condition" in str(value).lower() for value in adapter.inputs)


def test_truncated_generator_code_fence_is_a_retryable_validation_error() -> None:
    with pytest.raises(ValueError, match="truncated"):
        _parse("```", {"task": "release an invoice"})
