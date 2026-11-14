
from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    *,
    k: int = 60,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    if k < 0:
        raise ValueError("k must be zero or greater")
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("weights must match the number of rankings")
    scores: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights, strict=True):
        seen: set[str] = set()
        for rank, item_id in enumerate(ranking, start=1):
            if item_id in seen:
                continue
            seen.add(item_id)
            scores[item_id] += weight / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
