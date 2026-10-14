"""Explicit model-role routing and provenance capture."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .types import ModelProfile


class ModelRole(StrEnum):
    TESTED = "TESTED"
    GENERATOR = "GENERATOR"
    VALIDATOR = "VALIDATOR"
    JUDGE = "JUDGE"
    SYNTHETIC_PERSONA = "SYNTHETIC_PERSONA"


@dataclass(frozen=True)
class RoutedModel:
    role: ModelRole
    profile: ModelProfile
    provenance: Mapping[str, Any]


class ModelRoleRouter:
    def __init__(self, profiles: Mapping[ModelRole | str, ModelProfile], *, require_independent_support_roles: bool = True) -> None:
        self._profiles = {ModelRole(role): profile for role, profile in profiles.items()}
        self.require_independent_support_roles = require_independent_support_roles
        self.history: list[Mapping[str, Any]] = []
        self._validate()

    def route(self, role: ModelRole | str, *, artifact_kind: str, artifact_id: str | None = None) -> RoutedModel:
        selected_role = ModelRole(role)
        try:
            profile = self._profiles[selected_role]
        except KeyError as exc:
            raise ValueError(f"no model configured for role: {selected_role.value}") from exc
        record = {
            "role": selected_role.value,
            "provider": profile.provider,
            "model_id": profile.model_id,
            "artifact_kind": artifact_kind,
            "artifact_id": artifact_id,
        }
        self.history.append(record)
        return RoutedModel(selected_role, profile, record)

    def provenance_for(self, artifact_id: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(record for record in self.history if record.get("artifact_id") == artifact_id)

    def _validate(self) -> None:
        tested = self._profiles.get(ModelRole.TESTED)
        if tested is None:
            raise ValueError("TESTED model profile is required")
        if not self.require_independent_support_roles:
            return
        for role in (ModelRole.GENERATOR, ModelRole.VALIDATOR, ModelRole.JUDGE):
            profile = self._profiles.get(role)
            if profile is not None and profile.model_id == tested.model_id:
                raise ValueError(f"{role.value} cannot silently reuse TESTED model: {tested.model_id}")
