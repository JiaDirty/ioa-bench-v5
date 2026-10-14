import asyncio

from ioabench.generation.validators.semantic import SemanticValidator, SemanticVerdict, ValidatorArbitrator


def test_material_disagreement_invokes_arbitration_and_keeps_provenance() -> None:
    calls: list[str] = []

    def make(label: str, validator_id: str):
        def judge(context: dict[str, object]) -> SemanticVerdict:
            calls.append(validator_id)
            return SemanticVerdict(validator_id, label, 0.8, (), {})
        return SemanticValidator(validator_id, judge)

    result = asyncio.run(ValidatorArbitrator(make("PASS", "primary"), make("FAIL", "secondary"), make("PASS", "arbiter")).validate({"text": "visible"}))
    assert calls == ["primary", "secondary", "arbiter"]
    assert [verdict.validator_id for verdict in result] == ["primary", "secondary", "arbiter"]
