from ioabench.suites.t321.generation import T321Generator, T321_WORLDS

def test_t321_generation_truth_and_worlds() -> None:
    cases = [T321Generator().generate(mechanism_index=i, world_id=world, seed=i + 1) for i, world in enumerate(T321_WORLDS)]
    assert {case.world_id for case in cases} == set(T321_WORLDS)
    assert all(case.ground_truth.as_dict()["downgrade_present"] is True for case in cases)


def test_t321_control_and_risk_candidate_ids_are_distinct() -> None:
    generator = T321Generator()
    control = generator.generate(condition="CONTROL")
    risk = generator.generate(condition="RISK")
    assert control.candidate_id != risk.candidate_id
    assert control.naturalize({}).provenance["pair_id"] == risk.naturalize({}).provenance["pair_id"]
