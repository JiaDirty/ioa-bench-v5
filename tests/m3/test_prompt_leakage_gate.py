from ioabench.generation.leakage import find_prompt_leaks
from ioabench.suites.t312.generation import T312Generator
from ioabench.suites.t313.generation import T313Generator


def test_future_generators_do_not_encode_prescriptive_safety_advice() -> None:
    for generator in (T312Generator(), T313Generator()):
        skeleton = generator.generate(seed=7, mechanism_index=0, difficulty="hard", condition="RISK")
        assert not find_prompt_leaks(skeleton.sut_payload)


def test_prompt_leakage_gate_detects_direct_strategy_hint() -> None:
    assert find_prompt_leaks({"message": "This should be checked before action."})
