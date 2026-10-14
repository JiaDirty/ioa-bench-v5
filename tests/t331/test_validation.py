from ioabench.suites.t331.generation import T331Generator
from ioabench.suites.t331.validators import T331Validator


def test_t331_validator_does_not_replace_programmatic_truth() -> None:
    candidate = T331Generator().generate().naturalize({"summary": "verify before forwarding"})
    result = T331Validator().validate(candidate, semantic_ok=False)
    assert result.accepted and result.truth_consistent and not result.semantic_ok
