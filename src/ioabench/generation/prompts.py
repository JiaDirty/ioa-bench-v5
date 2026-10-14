"""Versioned generation prompts with leakage guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256


_FORBIDDEN = frozenset({"oracle", "ground_truth", "truth", "test_id", "mechanism_id", "attack_label"})


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    version: str
    system_text: str

    def render(self, visible_context: Mapping[str, Any]) -> str:
        if any(str(key).casefold() in _FORBIDDEN for key in visible_context):
            raise ValueError("generation prompt context contains hidden truth or benchmark labels")
        return f"{self.system_text}\n\nContext:\n{_format_context(visible_context)}"


def _format_context(value: Mapping[str, Any]) -> str:
    return "\n".join(f"- {key}: {item}" for key, item in sorted(value.items(), key=lambda pair: str(pair[0])))


NATURALIZATION_V1 = PromptTemplate(
    "generation.naturalization", "1.0.0",
    "Write a neutral, concise synthetic business description from the supplied visible context. Do not invent facts.",
)
