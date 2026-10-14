"""Machine-readable rejection distributions for generator improvement."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping


def summarize_rejections(records: Iterable[Mapping[str, object]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        code = record.get("code")
        if code and record.get("passed") is False:
            counts[str(code)] += 1
    return dict(sorted(counts.items()))
