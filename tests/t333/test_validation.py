from ioabench.suites.t333.generation import T333Generator
from ioabench.suites.t333.validators import T333Validator


def test_t333_validation_preserves_truth() -> None:
    result = T333Validator().validate(T333Generator().generate().naturalize({"trace": "periodic activity"}), semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
