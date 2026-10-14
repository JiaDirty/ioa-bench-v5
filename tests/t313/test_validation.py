from ioabench.suites.t313.generation import T313Generator
from ioabench.suites.t313.validators import T313Validator

def test_t313_validation_preserves_truth() -> None:
    result = T313Validator().validate(T313Generator().generate().naturalize({"message": "check each hop"}), semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
