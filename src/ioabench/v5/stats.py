"""Pure-Python statistics for the v5 analysis plan (docs/v5/V5_03_STATISTICAL_ANALYSIS_PLAN.md).

No third-party numerics, so every reported interval is reproducible from this file alone. All random
procedures take an explicit seed.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Hashable, Iterable, Mapping, Sequence

STATS_VERSION = "v5-stats-1.0.0"
Z95 = 1.959963984540054


# --------------------------------------------------------------------------- single proportions

def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) via a Lentz continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _betainc(b, a, 1 - x)
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(400):
        m = i // 2
        if i == 0:
            numerator = 1.0
        elif i % 2 == 0:
            numerator = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        d = 1e-30 if abs(d) < 1e-30 else d
        d = 1.0 / d
        c = 1.0 + numerator / c
        c = 1e-30 if abs(c) < 1e-30 else c
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (f - 1.0)


def _beta_ppf(q: float, a: float, b: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    lower = 0.0 if successes == 0 else _beta_ppf(alpha / 2, successes, n - successes + 1)
    upper = 1.0 if successes == n else _beta_ppf(1 - alpha / 2, successes + 1, n - successes)
    return (lower, upper)


# --------------------------------------------------------------------------- paired difference

def paired_delta(pairs: Sequence[tuple[bool, bool]]) -> float:
    """Delta = P(risk) - P(control) for (control_unsafe, risk_unsafe) pairs."""
    if not pairs:
        return math.nan
    return sum(r for _, r in pairs) / len(pairs) - sum(c for c, _ in pairs) / len(pairs)


def newcombe_paired(pairs: Sequence[tuple[bool, bool]], z: float = Z95) -> tuple[float, float]:
    """Newcombe (1998) method 10 interval for a paired difference of proportions (risk - control)."""
    n = len(pairs)
    if n == 0:
        return (math.nan, math.nan)
    both = sum(c and r for c, r in pairs)
    risk_only = sum((not c) and r for c, r in pairs)
    control_only = sum(c and (not r) for c, r in pairs)
    neither = n - both - risk_only - control_only
    p1, p2 = (both + risk_only) / n, (both + control_only) / n
    l1, u1 = wilson(both + risk_only, n, z)
    l2, u2 = wilson(both + control_only, n, z)
    denom = math.sqrt((both + risk_only) * (control_only + neither) * (both + control_only) * (risk_only + neither))
    numerator = both * neither - risk_only * control_only
    phi = 0.0 if denom == 0 else (max(numerator - n / 2, 0.0) if numerator > 0 else numerator) / denom
    d = p1 - p2
    dl = math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    du = math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return (max(-1.0, d - dl), min(1.0, d + du))


def _percentile(draws: list[float], alpha: float) -> tuple[float, float]:
    draws.sort()
    reps = len(draws)
    return (draws[int(math.floor(alpha / 2 * reps))], draws[min(reps - 1, int(math.ceil((1 - alpha / 2) * reps)) - 1)])


def cluster_bootstrap_delta(pairs: Sequence[tuple[Hashable, bool, bool]], *, reps: int = 10000, seed: int = 20261004,
                            alpha: float = 0.05) -> dict[str, float]:
    """Family-clustered percentile bootstrap for Delta. ``pairs`` = (family_id, control_unsafe, risk_unsafe)."""
    by_family: dict[Hashable, list[tuple[bool, bool]]] = defaultdict(list)
    for family, control, risk in pairs:
        by_family[family].append((control, risk))
    families = list(by_family)
    if not families:
        return {"delta": math.nan, "lower": math.nan, "upper": math.nan, "families": 0, "pairs": 0}
    point = paired_delta([p for f in families for p in by_family[f]])
    rng = random.Random(seed)
    draws = [paired_delta([p for f in (rng.choice(families) for _ in families) for p in by_family[f]])
             for _ in range(reps)]
    lower, upper = _percentile(draws, alpha)
    return {"delta": point, "lower": lower, "upper": upper, "families": len(families), "pairs": len(pairs),
            "reps": reps, "seed": seed}


def cluster_bootstrap_rate(rows: Sequence[tuple[Hashable, bool]], *, reps: int = 10000, seed: int = 20261004,
                           alpha: float = 0.05) -> dict[str, float]:
    by_family: dict[Hashable, list[bool]] = defaultdict(list)
    for family, value in rows:
        by_family[family].append(value)
    families = list(by_family)
    if not families:
        return {"rate": math.nan, "lower": math.nan, "upper": math.nan, "families": 0}
    point = sum(v for f in families for v in by_family[f]) / sum(len(by_family[f]) for f in families)
    rng = random.Random(seed)
    draws = []
    for _ in range(reps):
        sample = [v for f in (rng.choice(families) for _ in families) for v in by_family[f]]
        draws.append(sum(sample) / len(sample))
    lower, upper = _percentile(draws, alpha)
    return {"rate": point, "lower": lower, "upper": upper, "families": len(families)}


def sign_flip_p(pairs: Sequence[tuple[Hashable, bool, bool]], *, reps: int = 10000, seed: int = 20261004) -> float:
    """One-sided p for H0: Delta <= 0 via family-level sign-flip randomization of within-pair differences."""
    by_family: dict[Hashable, int] = defaultdict(int)
    for family, control, risk in pairs:
        by_family[family] += int(risk) - int(control)
    sums = list(by_family.values())
    observed = sum(sums)
    rng = random.Random(seed)
    hits = sum(sum(s if rng.random() < 0.5 else -s for s in sums) >= observed for _ in range(reps))
    return (hits + 1) / (reps + 1)


def holm(pvalues: Mapping[str, float], alpha: float = 0.05) -> dict[str, dict[str, float | bool]]:
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    m = len(ordered)
    out: dict[str, dict[str, float | bool]] = {}
    running = 0.0
    rejecting = True
    for rank, (key, p) in enumerate(ordered):
        running = min(1.0, max(running, (m - rank) * p))
        rejecting = rejecting and p <= alpha / (m - rank)
        out[key] = {"p": p, "p_holm": running, "reject": rejecting}
    return out


# --------------------------------------------------------------------------- missingness bounds

def missingness_bounds(eligible_pairs: Sequence[tuple[bool, bool]], missing_pairs: int) -> tuple[float, float]:
    """Delta bounds when ``missing_pairs`` scheduled pairs are non-eligible: worst/best-case imputation."""
    n = len(eligible_pairs) + missing_pairs
    if n == 0:
        return (math.nan, math.nan)
    risk = sum(r for _, r in eligible_pairs)
    control = sum(c for c, _ in eligible_pairs)
    return ((risk - (control + missing_pairs)) / n, ((risk + missing_pairs) - control) / n)


# --------------------------------------------------------------------------- agreement

def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("ratings must be non-empty and aligned")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def fleiss_kappa(ratings: Sequence[Sequence[Hashable]]) -> float:
    """``ratings[i]`` = labels for item i from the same number of raters (e.g. repeated runs)."""
    if not ratings:
        raise ValueError("no items")
    k = len(ratings[0])
    if k < 2 or any(len(r) != k for r in ratings):
        raise ValueError("each item needs the same number (>=2) of ratings")
    categories = sorted({x for r in ratings for x in r}, key=str)
    n = len(ratings)
    p_j = {c: sum(list(r).count(c) for r in ratings) / (n * k) for c in categories}
    p_i = [(sum(list(r).count(c) ** 2 for c in categories) - k) / (k * (k - 1)) for r in ratings]
    p_bar = sum(p_i) / n
    p_e = sum(v * v for v in p_j.values())
    return 1.0 if p_e == 1 else (p_bar - p_e) / (1 - p_e)


def krippendorff_alpha_nominal(units: Iterable[Sequence[Hashable | None]]) -> float:
    """Krippendorff's alpha (nominal) for units rated by possibly varying raters (None = missing)."""
    coincidences: Counter[tuple[Hashable, Hashable]] = Counter()
    for unit in units:
        values = [v for v in unit if v is not None]
        m = len(values)
        if m < 2:
            continue
        for i, x in enumerate(values):
            for j, y in enumerate(values):
                if i != j:
                    coincidences[(x, y)] += 1 / (m - 1)
    if not coincidences:
        return math.nan
    totals: Counter[Hashable] = Counter()
    for (x, _), weight in coincidences.items():
        totals[x] += weight
    n = sum(totals.values())
    observed = sum(w for (x, y), w in coincidences.items() if x != y)
    expected = sum(totals[x] * totals[y] for x in totals for y in totals if x != y) / (n - 1)
    return 1.0 if expected == 0 else 1 - observed / expected
