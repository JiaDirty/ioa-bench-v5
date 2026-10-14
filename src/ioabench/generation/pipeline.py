"""Small shared generation pipeline used by smoke and suite runners."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ioabench.datasets import DatasetStore

from .dedup import Deduplicator
from .difficulty import DifficultyCalibrator, DifficultyFeatures
from .leakage import find_leaks
from .repair import BoundedRepair
from .skeleton import CaseSkeleton, CandidateCase
from .validators.deterministic import DeterministicValidator


@dataclass(frozen=True)
class GenerationRun:
    accepted: tuple[CandidateCase, ...]
    rejected: tuple[Mapping[str, Any], ...]
    dataset_path: Path

    def report(self) -> dict[str, Any]:
        return {"accepted": len(self.accepted), "rejected": len(self.rejected), "dataset_path": str(self.dataset_path)}


class GenerationPipeline:
    def __init__(self, store: DatasetStore, *, validator: DeterministicValidator | None = None) -> None:
        self.store = store
        self.validator = validator or DeterministicValidator()

    def run(
        self,
        skeletons: Iterable[CaseSkeleton],
        *,
        manifest: Mapping[str, Any],
        naturalizer: Callable[[CaseSkeleton], Mapping[str, Any]] | None = None,
        features: Callable[[CaseSkeleton], DifficultyFeatures] | None = None,
        case_validator: Callable[[CandidateCase], bool] | None = None,
    ) -> GenerationRun:
        dedup = {"CONTROL": Deduplicator(), "RISK": Deduplicator()}
        calibrator = DifficultyCalibrator()
        repair = BoundedRepair(self.validator)
        accepted: list[CandidateCase] = []
        rejected: list[Mapping[str, Any]] = []
        for skeleton in skeletons:
            try:
                candidate = skeleton.naturalize(naturalizer(skeleton) if naturalizer else {})
                result = repair.run(candidate, lambda value: value)
                if result.status == "REGENERATE":
                    rejected.append({"candidate_id": candidate.candidate_id, "provenance": dict(candidate.provenance), "reason": "deterministic_validation", "findings": [asdict(item) for item in result.findings]})
                    continue
                if case_validator is not None and not case_validator(candidate):
                    rejected.append({"candidate_id": candidate.candidate_id, "provenance": dict(candidate.provenance), "reason": "suite_causal_validation"})
                    continue
                leaks = find_leaks(candidate.sut_payload, candidate.oracle_payload)
                if leaks:
                    rejected.append({"candidate_id": candidate.candidate_id, "provenance": dict(candidate.provenance), "reason": "oracle_leakage", "leaks": leaks})
                    continue
                if not dedup[skeleton.condition].add(candidate.sut_payload):
                    rejected.append({"candidate_id": candidate.candidate_id, "provenance": dict(candidate.provenance), "reason": "duplicate"})
                    continue
                measured = features(skeleton) if features else DifficultyFeatures()
                if features is not None and calibrator.classify(measured) != skeleton.difficulty:
                    rejected.append({"candidate_id": candidate.candidate_id, "provenance": dict(candidate.provenance), "reason": "difficulty_miscalibrated", "measured_score": measured.score()})
                    continue
                calibrated = calibrator.calibrate(candidate, measured, skeleton.difficulty)
                accepted.append(calibrated)
            except Exception as exc:
                rejected.append({"candidate_id": skeleton.candidate_id, "provenance": dict(skeleton.naturalize({}).provenance), "reason": type(exc).__name__, "detail": str(exc)})
        case_records = [asdict(candidate) for candidate in accepted]
        dataset_path = self.store.freeze(manifest, case_records, rejected)
        return GenerationRun(tuple(accepted), tuple(rejected), dataset_path)
