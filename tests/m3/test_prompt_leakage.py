import pytest

from ioabench.generation.prompts import NATURALIZATION_V1


def test_generation_prompt_rejects_hidden_truth_and_benchmark_labels() -> None:
    with pytest.raises(ValueError):
        NATURALIZATION_V1.render({"test_id": "T311", "description": "agent"})
    with pytest.raises(ValueError):
        NATURALIZATION_V1.render({"ground_truth": {"valid": False}})
