"""Deterministic pair sampling for pre-registered v5 review and pilot strata."""
from __future__ import annotations

import random
from itertools import combinations
from typing import Any


def select_pairs(pairs: list[tuple[Any, Any]], *, seed: str, strata: tuple[str, ...],
                 per_stratum: int = 2, distinct_fields: tuple[str, ...] = ("subtype",)) -> list[tuple[Any, Any]]:
    rng = random.Random(seed)
    selected: list[tuple[Any, Any]] = []
    for stratum in strata:
        pool = [pair for pair in pairs if pair[0].difficulty == stratum]
        rng.shuffle(pool)
        chosen = next((candidate for candidate in combinations(pool, per_stratum)
                       if all(len({getattr(pair[0], field) for pair in candidate}) == per_stratum
                              for field in distinct_fields)), None)
        if chosen is None:
            raise ValueError(f"{stratum} stratum requires {per_stratum} pairs with distinct {distinct_fields}")
        selected.extend(chosen)
    return selected
