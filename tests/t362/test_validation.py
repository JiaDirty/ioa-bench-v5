from ioabench.suites.t362.generation import T362Generator
from ioabench.suites.t362.validators import T362Validator
def test_t362_validation() -> None:
    result = T362Validator().validate(T362Generator().generate().naturalize({"discussion": "compare views"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
