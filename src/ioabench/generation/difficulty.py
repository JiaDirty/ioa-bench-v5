"""Explicit, truth-preserving Easy/Medium/Hard calibration."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .skeleton import CandidateCase


@dataclass(frozen=True)
class DifficultyFeatures:
    ambiguity: int = 0
    evidence_conflict: int = 0
    delegation_depth: int = 0
    peer_signals: int = 0
    distractor_density: int = 0
    timing_ambiguity: int = 0

    def score(self) -> int:
        return sum(max(0, value) for value in self.__dict__.values())


class DifficultyCalibrator:
    def classify(self, features: DifficultyFeatures) -> str:
        score = features.score()
        return "easy" if score <= 3 else "medium" if score <= 8 else "hard"

    def calibrate(self, candidate: CandidateCase, features: DifficultyFeatures, target: str | None = None) -> CandidateCase:
        difficulty = target or self.classify(features)
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be easy, medium or hard")
        return replace(candidate, difficulty=difficulty)
