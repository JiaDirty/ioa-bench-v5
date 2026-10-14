import pytest

from ioabench.suites.t311.generation import T311Generator, T311_WORLDS
from ioabench.suites.t311.scenario import T311ExposureController, T311Scenario


def test_t311_generator_uses_programmatic_truth_and_three_worlds() -> None:
    generator = T311Generator()
    cases = [generator.generate(mechanism_index=index, world_id=world, seed=index + 1) for index, world in enumerate(T311_WORLDS)]
    assert {case.world_id for case in cases} == set(T311_WORLDS)
    assert all(not all(case.ground_truth.as_dict()[key] for key in ("identity_valid", "capability_valid", "organization_qualified", "representation_valid")) for case in cases)
    assert all(case.condition == "RISK" for case in cases)
    with pytest.raises(ValueError):
        generator.generate(world_id="public-internet")


@pytest.mark.parametrize("mechanism_index", range(5))
def test_t311_paired_exposure_is_identical_until_authoritative_lookup(mechanism_index: int) -> None:
    generator = T311Generator()
    risk = generator.generate(mechanism_index=mechanism_index, seed=mechanism_index + 1, condition="RISK")
    control = generator.generate(mechanism_index=mechanism_index, seed=mechanism_index + 1, condition="CONTROL")
    risk_input: list[object] = []
    control_input: list[object] = []
    T311ExposureController().expose(T311Scenario("risk", "1.0.0", risk, ()), risk_input.append)
    T311ExposureController().expose(T311Scenario("control", "1.0.0", control, ()), control_input.append)
    assert risk_input == control_input
    assert "verification_records" not in str(risk_input)
    assert risk.sut_payload["verification_records"] != control.sut_payload["verification_records"]
    assert generator.difficulty_features(risk).score() <= 3
