"""Reference-value tests for the v5 statistics toolkit."""
from __future__ import annotations

import math

from ioabench.v5 import stats


def test_wilson_and_clopper_pearson_reference_values() -> None:
    lo, hi = stats.wilson(8, 10)
    assert math.isclose(lo, 0.4902, abs_tol=1e-4) and math.isclose(hi, 0.9433, abs_tol=1e-4)
    lo, hi = stats.clopper_pearson(8, 10)
    assert math.isclose(lo, 0.4439, abs_tol=1e-4) and math.isclose(hi, 0.9748, abs_tol=1e-4)
    assert stats.clopper_pearson(0, 20)[0] == 0.0


def test_krippendorff_alpha_reference_example() -> None:
    # Krippendorff (2011) "Computing Krippendorff's alpha-reliability", nominal example with missing data
    a = [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None]
    b = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3]
    c = [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None]
    d = [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None]
    alpha = stats.krippendorff_alpha_nominal(list(zip(a, b, c, d)))
    assert math.isclose(alpha, 0.743, abs_tol=1e-3)


def test_fleiss_kappa_reference_example() -> None:
    # Fleiss kappa worked example (14 raters, 10 subjects, 5 categories) -> 0.210
    counts = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
              [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    ratings = [[cat for cat, n in enumerate(row) for _ in range(n)] for row in counts]
    assert math.isclose(stats.fleiss_kappa(ratings), 0.210, abs_tol=1e-3)


def test_cohen_kappa_and_holm() -> None:
    assert stats.cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert math.isclose(stats.cohen_kappa(["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15,
                                          ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15), 0.4, abs_tol=1e-9)
    out = stats.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert out["a"]["reject"] and not out["b"]["reject"]
    assert math.isclose(float(out["a"]["p_holm"]), 0.03)


def test_paired_delta_intervals_cover_point_and_detect_effect() -> None:
    pairs = [(False, True)] * 20 + [(False, False)] * 35 + [(True, True)] * 3 + [(True, False)] * 2
    point = stats.paired_delta(pairs)
    assert math.isclose(point, 18 / 60)
    lo, hi = stats.newcombe_paired(pairs)
    assert lo < point < hi and lo > 0
    clustered = [(f"F{i // 2}", c, r) for i, (c, r) in enumerate(pairs)]
    boot = stats.cluster_bootstrap_delta(clustered, reps=2000, seed=1)
    assert boot["lower"] < point < boot["upper"] and boot["families"] == 30
    assert stats.sign_flip_p(clustered, reps=2000, seed=1) < 0.01
    null = [(f"F{i // 2}", i % 2 == 0, i % 4 == 0) for i in range(60)]
    assert stats.sign_flip_p(null, reps=2000, seed=1) > 0.05


def test_missingness_bounds_bracket_delta() -> None:
    pairs = [(False, True)] * 10 + [(False, False)] * 40
    lo, hi = stats.missingness_bounds(pairs, 10)
    assert lo < stats.paired_delta(pairs) < hi
