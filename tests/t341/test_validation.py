from ioabench.suites.t341.generation import T341Generator
from ioabench.suites.t341.validators import T341Validator
def test_t341_validation() -> None:
    result = T341Validator().validate(T341Generator().generate().naturalize({"evidence": "distributed"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
