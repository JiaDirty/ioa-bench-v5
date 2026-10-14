"""Generation-task routing over the existing provider-neutral role router."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ioabench.models import ModelRole, ModelRoleRouter, RoutedModel


class GenerationTask(StrEnum):
    NATURALIZATION = "NATURALIZATION"
    SEMANTIC_VALIDATION = "SEMANTIC_VALIDATION"
    JUDGE = "JUDGE"


@dataclass(frozen=True)
class GenerationRoute:
    task: GenerationTask
    routed_model: RoutedModel


class GenerationModelRouter:
    _ROLE_BY_TASK = {
        GenerationTask.NATURALIZATION: ModelRole.GENERATOR,
        GenerationTask.SEMANTIC_VALIDATION: ModelRole.VALIDATOR,
        GenerationTask.JUDGE: ModelRole.JUDGE,
    }

    def __init__(self, role_router: ModelRoleRouter) -> None:
        self.role_router = role_router

    def route(self, task: GenerationTask | str, *, artifact_id: str | None = None) -> GenerationRoute:
        selected = GenerationTask(task)
        routed = self.role_router.route(self._ROLE_BY_TASK[selected], artifact_kind=selected.value, artifact_id=artifact_id)
        return GenerationRoute(selected, routed)
