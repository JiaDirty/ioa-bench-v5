from collections import Counter

from ioabench.datasets import DatasetStore
from ioabench.generation.pipeline import GenerationPipeline
from ioabench.suites.t311.generation import T311Generator, T311_WORLDS
from ioabench.suites.t311.validators import T311Validator


def test_t311_formal_candidate_preflight_retains_causal_pairs(tmp_path) -> None:
    generator = T311Generator()
    validator = T311Validator()
    skeletons = [
        generator.generate(
            mechanism_index=(pair_index // 9) % 5,
            world_id=T311_WORLDS[(pair_index // 3) % 3],
            difficulty=("easy", "medium", "hard")[pair_index % 3],
            seed=pair_index + 1,
            condition=condition,
        )
        for pair_index in range(90)
        for condition in ("CONTROL", "RISK")
    ]
    manifest = {
        "schema_version": "1.0", "dataset_id": "T311-preflight", "test_id": "T311", "version": "0.0.1", "status": "FROZEN",
        "target": {"qualified_cases": 90, "difficulty": {"easy": 30, "medium": 30, "hard": 30}},
        "generation": {"generator_version": "t311-formal-v3", "mechanism_template_versions": ["T311-M01@0.1.0"], "world_ids": list(T311_WORLDS), "candidate_target_min": 180, "model_routing_policy": "offline-preflight"},
        "quality_gates": {"schema_valid": True, "oracle_consistent": True, "exposure_reachable": True, "control_solvable": True, "no_truth_leakage": True, "semantic_validation": "SINGLE_VALIDATOR"},
        "splits": {"development": 0.0, "formal": 1.0},
        "provenance_policy": {"retain_rejected": True, "record_model_calls": True, "record_prompt_versions": True},
    }
    generated = GenerationPipeline(DatasetStore(tmp_path)).run(
        skeletons, manifest=manifest, naturalizer=generator.naturalize,
        features=generator.difficulty_features,
        case_validator=lambda candidate: validator.validate(candidate).accepted,
    )
    accepted = generated.accepted
    counts = Counter(candidate.difficulty for candidate in accepted)
    pairs = Counter(candidate.provenance["pair_id"] for candidate in accepted)
    assert all(counts[difficulty] >= 30 for difficulty in ("easy", "medium", "hard"))
    assert sum(count == 2 for count in pairs.values()) >= 45
    assert {candidate.mechanism_id for candidate in accepted} == {f"T311-M{index:02d}" for index in range(1, 6)}
    assert {candidate.world_id for candidate in accepted} == set(T311_WORLDS)
    assert all(validator.validate(candidate).accepted for candidate in accepted)
