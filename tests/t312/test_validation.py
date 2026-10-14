from ioabench.suites.t312.generation import T312Generator
from ioabench.suites.t312.validators import T312Validator


def test_t312_validator_keeps_truth_external() -> None:
    skeleton = T312Generator().generate()
    candidate = skeleton.naturalize({"description": "highly visible executor"})
    result = T312Validator().validate(candidate, semantic_ok=False)
    assert result.accepted is True
    assert result.truth_consistent is True
    assert result.semantic_ok is False
