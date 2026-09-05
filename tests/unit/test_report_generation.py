import json

from taxi_pipeline.profiling.report import markdown_report, write_json


def _yellow(year, month, cbd):
    return {
        "file": {"year": year, "month": month, "row_count": 2, "file_size_bytes": 10,
                 "checksum_sha256": "a" * 64},
        "schema": {"normalized": [{"ordinal_position": 0, "name": "id", "arrow_type": "int64",
                                     "nullable": True}]},
        "columns": [{"name": "id", "null_count": 0, "null_rate": 0.0}],
        "observed_domains": {"VendorID": {"null_count": 0, "values": [{"value": 1, "count": 2}]}},
        "numeric_distributions": {"fare_amount": {"null_count": 0, "minimum": 0.0, "p01": 0.1,
            "p50": 1.0, "p95": 2.0, "p99": 2.0, "maximum": 2.0, "count_lt_0": 0,
            "count_eq_0": 1, "count_gt_0": 1}},
        "datetimes": {"tpep_pickup_datetime": {"minimum": "2025-01-01", "maximum": "2025-01-02"},
            "tpep_dropoff_datetime": {"minimum": "2025-01-01", "maximum": "2025-01-02"},
            "trip_duration_seconds": {"minimum": 0, "p50": 60.0, "p99": 120.0, "maximum": 120,
                "pickup_outside_nominal_month_count": 0, "dropoff_before_pickup_count": 0}},
        "taxi_zone_references": {"PULocationID": {"null_count": 0, "matched_count": 2,
            "unmatched_count": 0, "unmatched_rate_among_non_null": 0.0, "unmatched_ids": []}},
        "exact_duplicate_source_rows": {"total_rows": 2, "unique_full_rows": 2,
            "rows_participating_in_duplicate_groups": 0, "duplicate_excess_rows": 0,
            "duplicate_groups": 0},
    }


def test_json_and_markdown_are_deterministic_and_portable(tmp_path):
    old, new = _yellow(2024, 12, False), _yellow(2025, 1, True)
    zones = _yellow(None, None, False)
    zones["location_id"] = {"unique_count": 2, "duplicate_count": 0, "minimum": 1, "maximum": 2}
    zones["observed_domains"] = {}
    comparison = {"columns_only_in_yellow_2024_12": [], "columns_only_in_yellow_2025_01": ["cbd_congestion_fee"],
                  "type_differences": [], "nullability_differences": [], "column_order_difference": True,
                  "cbd_congestion_fee": {"yellow_2024_12": False, "yellow_2025_01": True}}
    path = tmp_path / "profile.json"
    write_json(path, {"local_path": "data/landing/file.parquet"})
    assert json.loads(path.read_text(encoding="utf-8"))["local_path"].startswith("data/")
    assert str(tmp_path) not in path.read_text(encoding="utf-8")
    first = markdown_report([old, new], zones, comparison)
    assert first == markdown_report([old, new], zones, comparison)
    assert "## Open Decisions for Architecture Review" in first
