from ioabench.suites.t352.generation import T352Generator
from ioabench.suites.t352.validators import T352Validator
def test_t352_validation() -> None:
    result = T352Validator().validate(T352Generator().generate().naturalize({"request": "compare alternatives"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
