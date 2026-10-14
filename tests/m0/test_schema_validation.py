from pathlib import Path

from jsonschema import Draft202012Validator

from ioabench.contracts import assert_valid, load_document


ROOT = Path(__file__).parents[2]
SCHEMA_ROOT = ROOT / "contracts" / "schema"


def test_shipped_schemas_and_example_validate() -> None:
    for schema_path in SCHEMA_ROOT.glob("*.schema.json"):
        schema = load_document(schema_path)
        Draft202012Validator.check_schema(schema)
    scenario = load_document(SCHEMA_ROOT / "example.T313.yaml")
    schema = load_document(SCHEMA_ROOT / "scenario.schema.json")
    assert_valid(scenario, schema)


def test_semantic_hooks_run_after_schema_validation() -> None:
    schema = {"type": "object", "required": ["value"]}
    document = {"value": 1}

    def hook(value: dict[str, object]):
        assert value["value"] == 1
        return ()

    assert_valid(document, schema, [hook])
