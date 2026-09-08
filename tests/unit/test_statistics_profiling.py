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
from taxi_pipeline.sources.contracts import (
    YELLOW_ADDITIVE_FIELD,
    YELLOW_BASELINE_FIELDS,
    YELLOW_FIELD_TYPES,
    validate_yellow_schema,
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


def test_exact_duplicates_are_independent_of_nullable_integer_batch_boundaries(tmp_path):
    path = tmp_path / "nullable-integers.parquet"
    table = pa.table(
        {
            "nullable_integer": pa.array([1, None, 1], type=pa.int64()),
            "label": pa.array(["same", "null-row", "same"], type=pa.large_string()),
        }
    )
    pq.write_table(table, path, row_group_size=2)
    expected = {
        "total_rows": 3,
        "unique_full_rows": 2,
        "rows_participating_in_duplicate_groups": 2,
        "duplicate_excess_rows": 1,
        "duplicate_groups": 1,
    }

    assert exact_duplicate_profile(path, batch_size=1) == expected
    assert exact_duplicate_profile(path, batch_size=2) == expected
    assert exact_duplicate_profile(path, batch_size=3) == expected


@pytest.mark.parametrize("batch_size", [1, 2, 3])
def test_exact_duplicates_normalize_signed_zero_across_batches(tmp_path, batch_size):
    path = tmp_path / "yellow-v2-signed-zero.parquet"
    names = [*YELLOW_BASELINE_FIELDS, YELLOW_ADDITIVE_FIELD]
    schema = pa.schema([pa.field(name, YELLOW_FIELD_TYPES[name]) for name in names])
    arrays = [
        pa.array([0.0, -0.0], type=field.type)
        if field.name == "fare_amount"
        else pa.array([None, None], type=field.type)
        for field in schema
    ]
    table = pa.Table.from_arrays(arrays, schema=schema)
    assert validate_yellow_schema(table.schema) == "yellow_v2"
    pq.write_table(table, path, row_group_size=1)

    assert exact_duplicate_profile(path, batch_size=batch_size) == {
        "total_rows": 2,
        "unique_full_rows": 1,
        "rows_participating_in_duplicate_groups": 2,
        "duplicate_excess_rows": 1,
        "duplicate_groups": 1,
    }


@pytest.mark.parametrize("batch_size", [1, 2, 3, 5])
def test_exact_duplicate_float_normalization_preserves_distinct_values(tmp_path, batch_size):
    path = tmp_path / "distinct-floats.parquet"
    table = pa.table(
        {
            "nullable_integer": pa.array([None, None, None, None], type=pa.int64()),
            "amount": pa.array([0.0, None, float("nan"), 1e-300], type=pa.float64()),
        }
    )
    pq.write_table(table, path, row_group_size=2)

    assert exact_duplicate_profile(path, batch_size=batch_size) == {
        "total_rows": 4,
        "unique_full_rows": 4,
        "rows_participating_in_duplicate_groups": 0,
        "duplicate_excess_rows": 0,
        "duplicate_groups": 0,
    }
