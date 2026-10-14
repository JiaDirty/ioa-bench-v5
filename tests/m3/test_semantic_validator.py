import asyncio

import pytest

from ioabench.generation.validators.semantic import SemanticValidator, SemanticVerdict


def test_semantic_validator_receives_only_visible_context_and_records_provenance() -> None:
    seen = []

    def judge(context: dict[str, object]) -> SemanticVerdict:
        seen.append(context)
        return SemanticVerdict("raw", "PASS", 0.9, ("e-1",), {})

    validator = SemanticValidator("validator-a", judge)
    verdict = asyncio.run(validator.validate({"description": "neutral", "evidence": ["e-1"]}))
    assert seen == [{"description": "neutral", "evidence": ["e-1"]}]
    assert verdict.metadata["validator_id"] == "validator-a"
    assert len(verdict.metadata["input_sha256"]) == 64
    with pytest.raises(ValueError):
        asyncio.run(validator.validate({"ground_truth": {"safe": True}}))
