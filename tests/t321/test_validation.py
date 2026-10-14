from ioabench.suites.t321.generation import T321Generator
from ioabench.suites.t321.validators import T321Validator

def test_t321_validation_preserves_truth() -> None:
    result = T321Validator().validate(T321Generator().generate().naturalize({"message": "compare capabilities"}), semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
