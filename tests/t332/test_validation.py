from ioabench.suites.t332.generation import T332Generator
from ioabench.suites.t332.validators import T332Validator


def test_t332_validation_preserves_truth() -> None:
    result = T332Validator().validate(T332Generator().generate().naturalize({"request": "map only what is needed"}), semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
