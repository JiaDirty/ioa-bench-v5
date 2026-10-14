"""Run a tiny AI-assisted T311 generation trial; never freezes a dataset."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from ioabench.generation.ai_naturalize import naturalize_t311_pairs
from ioabench.generation.pipeline import GenerationPipeline
from ioabench.datasets import DatasetStore
from ioabench.generation.ai_semantic import validate_candidates
from ioabench.suites.t311.generation import T311Generator, T311_WORLDS
from ioabench.suites.t311.validators import T311Validator


def run(root: Path, output: Path, generator_model: str, primary_model: str, secondary_model: str) -> dict:
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    generator = T311Generator()
    skeletons = [
        generator.generate(
            mechanism_index=0,
            world_id=T311_WORLDS[0],
            difficulty="easy",
            seed=9001,
            condition=condition,
        )
        for condition in ("CONTROL", "RISK")
    ]
    cache_path = output / "ai-naturalization.json"
    naturalizations, naturalization_failures = asyncio.run(
        naturalize_t311_pairs(skeletons, model_id=generator_model, cache_path=cache_path)
    )
    if naturalization_failures or len(naturalizations) != 1:
        raise RuntimeError(f"naturalization failed: {naturalization_failures}")

    def naturalizer(skeleton):
        base = generator.naturalize(skeleton)
        value = naturalizations[skeleton.naturalize({}).provenance["pair_id"]]
        base.update(value.visible())
        return base

    manifest = {
        "schema_version": "1.0",
        "dataset_id": "T311-generation-trial",
        "test_id": "T311",
        "version": "0.0.0",
        "status": "FROZEN",
        "generation": {
            "generator_version": "t311-generation-trial-1.0.0",
            "mechanism_template_versions": ["T311-M01@0.1.0"],
            "world_ids": [T311_WORLDS[0]],
            "candidate_target_min": 2,
            "generator_model_id": generator_model,
            "generator_prompt_version": "t311-neutral-naturalization-v1",
            "model_routing_policy": "aihubmix_generation_only",
        },
        "target": {"qualified_cases": 2, "difficulty": {"easy": 2, "medium": 0, "hard": 0}},
        "splits": {"development": 1.0, "formal": 0.0},
        "provenance_policy": {"retain_rejected": True, "record_model_calls": True, "record_prompt_versions": True},
        "quality_gates": {"schema_valid": True, "oracle_consistent": True, "exposure_reachable": True, "control_solvable": True, "no_truth_leakage": True, "semantic_validation": "DUAL_VALIDATOR"},
    }
    with TemporaryDirectory() as temporary_root:
        dataset = GenerationPipeline(DatasetStore(temporary_root)).run(
            skeletons,
            manifest=manifest,
            naturalizer=naturalizer,
            features=generator.difficulty_features,
            case_validator=lambda candidate: T311Validator().validate(candidate).accepted,
        )
    records = [asdict(case) for case in dataset.accepted]
    validations = asyncio.run(
        validate_candidates(
            records,
            primary_model=primary_model,
            secondary_model=secondary_model,
            cache_path=output / "semantic-validation.json",
        )
    )
    validation_summary = [
        {"candidate_id": item.candidate_id, "accepted": item.accepted, "verdicts": [asdict(verdict) for verdict in item.verdicts]}
        for item in validations
    ]
    (output / "cases.json").write_text(json.dumps(records, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = {
        "trial_id": "T311-generation-trial-1.0.0",
        "formal_dataset": False,
        "frozen": False,
        "provider_calls_expected": 3,
        "candidate_count": len(records),
        "naturalization_failures": naturalization_failures,
        "semantic_validation": validation_summary,
        "quality_gate": all(item["accepted"] for item in validation_summary) and len(records) == 2,
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generator-model", default="glm-5.2")
    parser.add_argument("--primary-model", default="glm-5.3-flash")
    parser.add_argument("--secondary-model", default="gpt-5.6-luna")
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[1], args.output, args.generator_model, args.primary_model, args.secondary_model), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
