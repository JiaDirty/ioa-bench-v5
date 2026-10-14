"""Content-addressed provenance for generated artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256


@dataclass(frozen=True)
class GenerationProvenance:
    artifact_id: str
    prompt_template_id: str
    prompt_version: str
    model_id: str
    settings: Mapping[str, Any]
    parent_ids: tuple[str, ...]
    input_sha256: str
    output_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def record_provenance(
    *, artifact_id: str, prompt_template_id: str, prompt_version: str, model_id: str,
    settings: Mapping[str, Any], parents: tuple[str, ...] | list[str] = (),
    prompt: Any, output: Any,
) -> GenerationProvenance:
    return GenerationProvenance(
        artifact_id, prompt_template_id, prompt_version, model_id, dict(settings), tuple(parents),
        canonical_sha256(prompt), canonical_sha256(output),
    )
