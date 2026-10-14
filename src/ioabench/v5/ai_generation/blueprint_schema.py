from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

# P3 selective integration: the canonical Blueprint JSON Schema travels with the package
DEFAULT_SCHEMA = Path(__file__).resolve().parent / "data" / "02_BLUEPRINT_SCHEMA.json"


def load_schema(path: Path | None = None) -> Mapping[str, Any]:
    return json.loads((path or DEFAULT_SCHEMA).read_text(encoding="utf-8"))


def validate_blueprint(value: Mapping[str, Any], *, schema_path: Path | None = None) -> list[dict[str, str]]:
    """Return stable, serializable schema findings; an empty list means valid."""
    validator = Draft202012Validator(load_schema(schema_path))
    return [
        {"code": "SCHEMA_INVALID", "field_path": "/" + "/".join(str(x) for x in error.absolute_path),
         "reason": error.message}
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    ]
