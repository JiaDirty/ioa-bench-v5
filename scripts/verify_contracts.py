"""Validate all shipped JSON Schemas and the bundled example scenario."""

from pathlib import Path

from jsonschema import Draft202012Validator

from ioabench.contracts import assert_valid, load_document


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "contracts" / "schema"


def main() -> int:
    schemas = {path.name: load_document(path) for path in SCHEMA_ROOT.glob("*.schema.json")}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    assert_valid(load_document(SCHEMA_ROOT / "example.T313.yaml"), schemas["scenario.schema.json"])
    print(f"validated {len(schemas)} JSON schemas and example.T313.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
