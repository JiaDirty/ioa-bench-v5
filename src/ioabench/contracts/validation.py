"""JSON Schema validation with suite-specific semantic hooks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import jsonschema
import yaml

from ioabench.errors import ContractError


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    message: str
    path: tuple[str, ...] = ()
    severity: str = "ERROR"


SemanticHook = Callable[[Mapping[str, Any]], Iterable[ValidationFinding]]


def load_document(path: str | Path) -> Any:
    document_path = Path(path)
    try:
        text = document_path.read_text(encoding="utf-8")
        return json.loads(text) if document_path.suffix == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ContractError(f"cannot load document: {document_path}") from exc


def validate_document(
    document: Any,
    schema: Mapping[str, Any],
    semantic_hooks: Iterable[SemanticHook] = (),
) -> tuple[ValidationFinding, ...]:
    try:
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    except jsonschema.SchemaError as exc:
        raise ContractError("invalid JSON Schema") from exc
    findings = [
        ValidationFinding(
            code="SCHEMA_VALIDATION_ERROR",
            message=error.message,
            path=tuple(str(part) for part in error.path),
        )
        for error in errors
    ]
    if not errors and isinstance(document, Mapping):
        for hook in semantic_hooks:
            findings.extend(hook(document))
    return tuple(findings)


def assert_valid(
    document: Any,
    schema: Mapping[str, Any],
    semantic_hooks: Iterable[SemanticHook] = (),
) -> None:
    findings = validate_document(document, schema, semantic_hooks)
    if findings:
        detail = "; ".join(f"{finding.code}: {finding.message}" for finding in findings)
        raise ContractError(detail)
