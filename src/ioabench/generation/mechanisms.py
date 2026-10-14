"""Provider-neutral mechanism template declarations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MechanismTemplate:
    mechanism_id: str
    test_id: str
    family: str
    truth_requirements: tuple[str, ...]
    exposure_requirements: tuple[str, ...]
    control_requirements: tuple[str, ...]
    difficulty_requirements: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.mechanism_id or not self.test_id or not self.family:
            raise ValueError("mechanism template identity is required")
        if not all((self.truth_requirements, self.exposure_requirements, self.control_requirements)):
            raise ValueError("mechanism template requirements cannot be empty")
