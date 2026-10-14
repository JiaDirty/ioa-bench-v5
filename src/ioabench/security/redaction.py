"""Redact environment secrets before telemetry or exception persistence."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, repr=False)
class SecretRedactor:
    secrets: tuple[str, ...]
    marker: str = "[REDACTED_SECRET]"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SecretRedactor":
        source = os.environ if environ is None else environ
        values = tuple(sorted({value for name, value in source.items() if name.endswith("_API_KEY") and value}, key=len, reverse=True))
        return cls(values)

    def text(self, value: str) -> str:
        result = value
        for secret in self.secrets:
            result = result.replace(secret, self.marker)
        return result

    def value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, Mapping):
            return {key: self.value(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            return [self.value(item) for item in value]
        return value

    def exception(self, error: BaseException) -> str:
        return self.text(str(error))

    def __repr__(self) -> str:
        return "SecretRedactor(<redacted>)"
