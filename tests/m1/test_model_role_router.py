import pytest

from ioabench.models import ModelProfile, ModelRole, ModelRoleRouter


def profile(model_id: str, role: str) -> ModelProfile:
    return ModelProfile("aihubmix", model_id, {}, {}, role)


def test_router_records_role_model_and_artifact_provenance() -> None:
    router = ModelRoleRouter({
        ModelRole.TESTED: profile("tested-model", "TESTED"),
        ModelRole.GENERATOR: profile("generator-model", "GENERATOR"),
        ModelRole.VALIDATOR: profile("validator-model", "VALIDATOR"),
        ModelRole.JUDGE: profile("judge-model", "JUDGE"),
    })

    routed = router.route(ModelRole.GENERATOR, artifact_kind="candidate", artifact_id="candidate-1")

    assert routed.profile.model_id == "generator-model"
    assert router.provenance_for("candidate-1")[0]["role"] == "GENERATOR"
    assert router.provenance_for("candidate-1")[0]["model_id"] == "generator-model"


def test_router_rejects_tested_model_reuse_for_support_roles() -> None:
    tested = profile("same-model", "TESTED")
    with pytest.raises(ValueError, match="cannot silently reuse"):
        ModelRoleRouter({
            ModelRole.TESTED: tested,
            ModelRole.GENERATOR: profile("same-model", "GENERATOR"),
        })


def test_router_allows_explicit_policy_override() -> None:
    router = ModelRoleRouter({ModelRole.TESTED: profile("same-model", "TESTED")}, require_independent_support_roles=False)
    assert router.route(ModelRole.TESTED, artifact_kind="run", artifact_id="run-1").role is ModelRole.TESTED
