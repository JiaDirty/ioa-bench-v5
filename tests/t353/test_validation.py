from ioabench.suites.t353.generation import T353Generator
from ioabench.suites.t353.validators import T353Validator
def test_t353_validation() -> None:
    result = T353Validator().validate(T353Generator().generate().naturalize({"request": "compare independent alternatives"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
