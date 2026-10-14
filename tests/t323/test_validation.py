from ioabench.suites.t323.generation import T323Generator
from ioabench.suites.t323.validators import T323Validator

def test_t323_validation_preserves_truth() -> None:
    result = T323Validator().validate(T323Generator().generate().naturalize({"message": "request provenance"}), semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
