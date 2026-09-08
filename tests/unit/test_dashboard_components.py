from taxi_pipeline.dashboard.components import (
    duration_label,
    format_percentage,
    monthly_frame,
    partition_label,
    status_label,
)


def test_dashboard_formatters_preserve_operational_meaning():
    assert status_label("skipped") == "– SKIPPED"
    assert partition_label(
        {"service_type": "yellow", "source_year": 2025, "source_month": 1}
    ) == "yellow 2025-01"
    assert duration_label("2025-01-01T00:00:00+00:00", "2025-01-01T00:01:05+00:00") == "1m 5s"
    assert format_percentage(0.000036) == "0.0036%"


def test_monthly_frame_keeps_unknown_analytics_bucket_visible():
    frame = monthly_frame(
        [
            {"month": None, "service_type": "yellow", "trip_count": 2},
            {"month": "2025-01-01", "service_type": "yellow", "trip_count": 4},
        ]
    )

    assert frame["month"].tolist() == ["Unknown", "2025-01-01"]


def test_dashboard_app_import_has_no_api_side_effect():
    from taxi_pipeline.dashboard import app

    assert app.DEFAULT_API_BASE_URL == "http://localhost:8000"
