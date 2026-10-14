from ioabench.suites.t322.generation import T322Generator
from ioabench.suites.t322.validators import T322Validator

def test_t322_validation_preserves_truth() -> None:
    result = T322Validator().validate(T322Generator().generate().naturalize({"message": "check state semantics"}), semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
