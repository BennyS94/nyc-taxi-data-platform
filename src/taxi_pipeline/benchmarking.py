"""Small statistics helpers shared by reproducible benchmark scripts."""

import math
from collections.abc import Sequence
from typing import TypeVar

Number = TypeVar("Number", int, float)


def nearest_rank_percentile(values: Sequence[Number], percentile: float) -> Number:
    """Return the empirical nearest-rank percentile from non-empty observations."""
    if not values:
        raise ValueError("percentile requires at least one observation")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be greater than 0 and at most 1")
    ordered = sorted(values)
    rank = math.ceil(percentile * len(ordered))
    return ordered[rank - 1]
