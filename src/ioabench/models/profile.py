"""Versioned model-profile loading."""

from __future__ import annotations

from pathlib import Path

from ioabench.contracts import assert_valid, load_document
from ioabench.models.types import ModelProfile


def load_model_profile(path: str | Path) -> ModelProfile:
    profile = load_document(path)
    schema_path = Path(__file__).resolve().parents[3] / "contracts" / "schema" / "model_profile.schema.json"
    assert_valid(profile, load_document(schema_path))
    return ModelProfile(
        provider=profile["provider"],
        model_id=profile["model_id"],
        capabilities=profile["capabilities"],
        default_parameters=profile.get("default_parameters", {}),
        role=profile["role"],
    )
