from ioabench.suites.t342.generation import T342Generator
from ioabench.suites.t342.validators import T342Validator
def test_t342_validation() -> None:
    result = T342Validator().validate(T342Generator().generate().naturalize({"message": "retain source"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
