from ioabench.suites.t351.generation import T351Generator
from ioabench.suites.t351.validators import T351Validator
def test_t351_validation() -> None:
    result = T351Validator().validate(T351Generator().generate().naturalize({"reward_notice": "preserve verification"}), semantic_ok=False); assert result.accepted and result.truth_consistent and not result.semantic_ok
