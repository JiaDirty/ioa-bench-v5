"""Load and validate the reusable synthetic-world library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ioabench.contracts import assert_valid, load_document


def load_world(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    world = load_document(root)
    schema = load_document(Path(__file__).resolve().parents[3] / "contracts" / "schema" / "world.schema.json")
    assert_valid(world, schema)
    return world


def load_worlds(root: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(load_world(path) for path in sorted(Path(root).glob("*.yaml")))


def load_roles(path: str | Path) -> dict[str, dict[str, Any]]:
    document = load_document(path)
    roles = document.get("roles", {})
    if not isinstance(roles, dict) or not roles:
        raise ValueError("role library must contain roles")
    return {str(role_id): dict(value) for role_id, value in roles.items()}
