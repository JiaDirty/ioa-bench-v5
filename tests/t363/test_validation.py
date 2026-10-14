from ioabench.suites.t363.generation import T363Generator
from ioabench.suites.t363.validators import T363Validator
def test_t363_validation() -> None:
    result = T363Validator().validate(T363Generator().generate().naturalize({"withdrawal": "independent task"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
