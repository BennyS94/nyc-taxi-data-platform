from datetime import datetime

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from taxi_pipeline.profiling.statistics import (
    domain_profile,
    duration_profile,
    exact_duplicate_profile,
    null_summary,
    numeric_profile,
    zone_reference_profile,
)


def test_null_numeric_and_domain_profiles():
    values = pa.chunked_array([[None, -2.0, 0.0, 2.0, 10.0]])
    assert null_summary(values) == {"null_count": 1, "null_rate": 0.2}
    result = numeric_profile(values)
    assert result["non_null_count"] == 4
    assert result["count_lt_0"] == result["count_eq_0"] == 1
    assert result["count_gt_0"] == 2
    assert result["p50"] == pytest.approx(1.0)
    domain = domain_profile(pa.chunked_array([[1, None, 9, 1]]))
    assert domain == {"null_count": 1, "values": [{"value": 1, "count": 2},
                                                    {"value": 9, "count": 1}]}


def test_duration_and_month_anomalies():
    pickup = pa.chunked_array([[datetime(2025, 1, 1), datetime(2025, 1, 2),  # noqa: DTZ001
                                datetime(2024, 12, 31), None]],  # noqa: DTZ001
                              type=pa.timestamp("us"))
    dropoff = pa.chunked_array([[datetime(2025, 1, 1),  # noqa: DTZ001
                                 datetime(2025, 1, 1, 23, 59),  # noqa: DTZ001
                                 datetime(2025, 1, 1),  # noqa: DTZ001
                                 datetime(2025, 1, 2)]],  # noqa: DTZ001
                               type=pa.timestamp("us"))
    result = duration_profile(pickup, dropoff, 2025, 1)
    assert result["count_eq_0"] == 1
    assert result["dropoff_before_pickup_count"] == 1
    assert result["either_datetime_null_count"] == 1
    assert result["pickup_outside_nominal_month_count"] == 1


def test_zone_reference_profile():
    result = zone_reference_profile(pa.chunked_array([[1, 2, 9, 9, None]]), {1, 2})
    assert result["matched_count"] == 2
    assert result["null_count"] == 1
    assert result["unmatched_count"] == 2
    assert result["unmatched_rate_among_non_null"] == 0.5
    assert result["unmatched_ids"] == [{"value": 9, "count": 2}]


def test_exact_duplicate_profile_verifies_complete_rows(tmp_path):
    path = tmp_path / "fixture.parquet"
    pq.write_table(pa.Table.from_pandas(pd.DataFrame({"a": [1, 1, 1, 2], "b": ["x", "x", "y", "z"]})), path)
    result = exact_duplicate_profile(path, batch_size=2)
    assert result == {
        "total_rows": 4, "unique_full_rows": 3,
        "rows_participating_in_duplicate_groups": 2,
        "duplicate_excess_rows": 1, "duplicate_groups": 1,
    }
