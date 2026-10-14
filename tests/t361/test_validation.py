from ioabench.suites.t361.generation import T361Generator
from ioabench.suites.t361.validators import T361Validator
def test_t361_validation() -> None:
    result = T361Validator().validate(T361Generator().generate().naturalize({"interaction": "verify"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
