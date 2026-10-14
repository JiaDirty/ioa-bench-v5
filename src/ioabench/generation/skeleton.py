"""Programmatic case skeletons and immutable Ground Truth."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256
from .truth import GroundTruth


_HIDDEN_KEYS = frozenset({"oracle", "oracle_ref", "oracle_payload", "ground_truth", "hidden_truth", "truth", "truth_label", "attack_label", "scoring_rules"})


def _reject_hidden(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in _HIDDEN_KEYS:
                raise ValueError(f"visible payload contains hidden field: {key}")
            _reject_hidden(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_hidden(item)


@dataclass(frozen=True)
class CandidateCase:
    candidate_id: str
    test_id: str
    mechanism_id: str
    world_id: str
    difficulty: str
    sut_payload: Mapping[str, Any]
    oracle_payload: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class CaseSkeleton:
    candidate_id: str
    test_id: str
    mechanism_id: str
    world_id: str
    difficulty: str
    seed: int
    sut_payload: Mapping[str, Any]
    ground_truth: GroundTruth
    condition: str = "RISK"

    def __post_init__(self) -> None:
        if self.condition not in {"CONTROL", "RISK"}:
            raise ValueError("condition must be CONTROL or RISK")
        if self.difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be easy, medium or hard")
        _reject_hidden(self.sut_payload)
        object.__setattr__(self, "sut_payload", deepcopy(dict(self.sut_payload)))

    def naturalize(self, visible_payload: Mapping[str, Any]) -> CandidateCase:
        _reject_hidden(visible_payload)
        if self.sut_payload.keys() & visible_payload.keys():
            raise ValueError("naturalized payload cannot replace programmatic skeleton fields")
        payload = deepcopy(dict(self.sut_payload))
        payload.update(deepcopy(dict(visible_payload)))
        provenance = {
            "seed": self.seed,
            "condition": self.condition,
            "pair_id": f"{self.test_id}-{self.mechanism_id}-{self.world_id}-{self.seed}",
            "skeleton_sha256": canonical_sha256(self.sut_payload),
            "oracle_sha256": self.ground_truth.content_sha256,
        }
        return CandidateCase(
            self.candidate_id, self.test_id, self.mechanism_id, self.world_id,
            self.difficulty, payload, self.ground_truth.as_dict(), provenance,
        )


def build_skeleton(
    *, candidate_id: str, test_id: str, mechanism_id: str, world_id: str,
    difficulty: str, seed: int, sut_payload: Mapping[str, Any], truth: Mapping[str, Any],
    condition: str = "RISK",
) -> CaseSkeleton:
    return CaseSkeleton(candidate_id, test_id, mechanism_id, world_id, difficulty, seed, dict(sut_payload), GroundTruth(truth), condition)


def paired_skeletons(**kwargs: Any) -> tuple[CaseSkeleton, CaseSkeleton]:
    control_sut_payload = kwargs.pop("control_sut_payload")
    control_truth = kwargs.pop("control_truth")
    if kwargs["sut_payload"] == control_sut_payload:
        raise ValueError("control must remove or correct the SUT-visible risk stimulus")
    risk = build_skeleton(**kwargs, condition="RISK")
    control = build_skeleton(**{**kwargs, "sut_payload": control_sut_payload, "truth": control_truth, "condition": "CONTROL", "candidate_id": f"{kwargs['candidate_id']}-control"})
    return control, risk
