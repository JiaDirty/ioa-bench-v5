from ioabench.suites.t343.generation import T343Generator
from ioabench.suites.t343.validators import T343Validator
def test_t343_validation() -> None:
    result = T343Validator().validate(T343Generator().generate().naturalize({"policy": "verify before action"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
