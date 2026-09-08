import pytest

from taxi_pipeline.benchmarking import nearest_rank_percentile


def test_nearest_rank_p95_uses_fifth_observation_for_five_samples():
    assert nearest_rank_percentile([30.0, 10.0, 50.0, 20.0, 40.0], 0.95) == 50.0


def test_nearest_rank_percentile_handles_sample_sizes_and_invalid_input():
    assert nearest_rank_percentile([3, 1, 2], 0.5) == 2
    assert nearest_rank_percentile([7], 0.95) == 7
    with pytest.raises(ValueError, match="at least one"):
        nearest_rank_percentile([], 0.95)
    with pytest.raises(ValueError, match="greater than 0"):
        nearest_rank_percentile([1], 0)
