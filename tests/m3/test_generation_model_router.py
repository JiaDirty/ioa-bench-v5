import pytest

from ioabench.generation.model_router import GenerationModelRouter, GenerationTask
from ioabench.models import ModelProfile, ModelRole, ModelRoleRouter


def test_generation_tasks_route_to_independent_roles_and_record_exact_ids() -> None:
    router = ModelRoleRouter({
        ModelRole.TESTED: ModelProfile("aihubmix", "deepseek-v4.1-flash", {}, {}),
        ModelRole.GENERATOR: ModelProfile("aihubmix", "qwen-generator", {}, {}, "GENERATOR"),
        ModelRole.VALIDATOR: ModelProfile("aihubmix", "glm-validator", {}, {}, "VALIDATOR"),
        ModelRole.JUDGE: ModelProfile("aihubmix", "gpt-judge", {}, {}, "JUDGE"),
    })
    generation = GenerationModelRouter(router)
    assert generation.route(GenerationTask.NATURALIZATION, artifact_id="a").routed_model.profile.model_id == "qwen-generator"
    assert generation.route("SEMANTIC_VALIDATION", artifact_id="b").routed_model.profile.model_id == "glm-validator"
    assert generation.route("JUDGE", artifact_id="c").routed_model.profile.model_id == "gpt-judge"
    assert [record["model_id"] for record in router.history] == ["qwen-generator", "glm-validator", "gpt-judge"]


def test_role_router_rejects_silent_tested_model_reuse() -> None:
    with pytest.raises(ValueError):
        ModelRoleRouter({
            ModelRole.TESTED: ModelProfile("mock", "same", {}, {}),
            ModelRole.GENERATOR: ModelProfile("mock", "same", {}, {}, "GENERATOR"),
        })
