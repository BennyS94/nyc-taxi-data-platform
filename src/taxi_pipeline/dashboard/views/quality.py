"""Persisted data-quality results view."""

from collections import Counter
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from taxi_pipeline.dashboard.components import (
    format_integer,
    format_percentage,
    partition_label,
    render_empty,
    render_metrics,
    status_label,
)

Loader = Callable[..., Any]


def render(load: Loader) -> None:
    st.title("Data Quality")
    service_label = st.selectbox("Service", ["All", "Yellow", "Green"])
    service_type = None if service_label == "All" else service_label.lower()
    runs = load("list_all_runs", service_type=service_type)
    eligible_runs = [run for run in runs if run["status"] == "succeeded"]
    if not eligible_runs:
        render_empty("No successful pipeline runs have quality results for this selection.")
        return

    run_id = st.selectbox(
        "Source Month / Run",
        [run["run_id"] for run in eligible_runs],
        format_func=lambda value: _run_option(value, eligible_runs),
    )
    left, right = st.columns(2)
    severity_label = left.selectbox("Severity", ["All", "INFO", "WARNING", "ERROR"])
    status_label_filter = right.selectbox("Status", ["All", "PASSED", "VIOLATED"])
    params = {
        "severity": None if severity_label == "All" else severity_label,
        "status": None if status_label_filter == "All" else status_label_filter.lower(),
    }
    results = load("get_run_quality", run_id, **params)
    if not results:
        render_empty("No quality results for this selection.")
        return

    warnings = sum(r["severity"] == "WARNING" and r["status"] == "violated" for r in results)
    errors = sum(r["severity"] == "ERROR" and r["status"] == "violated" for r in results)
    info = sum(r["severity"] == "INFO" for r in results)
    render_metrics(
        [
            ("Checks Run", format_integer(len(results))),
            ("Warnings Violated", format_integer(warnings)),
            ("Errors Violated", format_integer(errors)),
            ("Info Metrics", format_integer(info)),
        ]
    )

    rows = [
        {
            "Result ID": result["quality_result_id"],
            "Check": result["check_name"],
            "Severity": result["severity"],
            "Status": result["status"].upper(),
            "Rows Checked": result["rows_checked"],
            "Rows Failed": result["rows_failed"],
            "Failure Rate": format_percentage(result["failure_rate"]),
        }
        for result in results
    ]
    st.subheader("Quality Results")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    warnings_frame = pd.DataFrame(
        [r for r in results if r["severity"] == "WARNING" and r["status"] == "violated"]
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Warnings by Check")
        if warnings_frame.empty:
            render_empty("No violated warnings in this selection.")
        else:
            st.bar_chart(warnings_frame.set_index("check_name")[["rows_failed"]], horizontal=True)
    with right:
        st.subheader("Quality Results by Severity")
        severity_counts = Counter(result["severity"] for result in results)
        severity_frame = pd.DataFrame(
            [{"severity": key, "results": value} for key, value in severity_counts.items()]
        )
        st.bar_chart(severity_frame.set_index("severity"))

    result_id = st.selectbox(
        "Inspect Quality Result",
        [result["quality_result_id"] for result in results],
        format_func=lambda value: next(
            result["check_name"] for result in results if result["quality_result_id"] == value
        ),
    )
    selected = next(result for result in results if result["quality_result_id"] == result_id)
    st.markdown("#### Quality Detail")
    detail = {
        "Check": selected["check_name"],
        "Severity": selected["severity"],
        "Status": selected["status"].upper(),
        "Rows Checked": format_integer(selected["rows_checked"]),
        "Rows Failed": format_integer(selected["rows_failed"]),
        "Failure Rate": format_percentage(selected["failure_rate"]),
        "Executed At": selected["executed_at"],
    }
    for label, value in detail.items():
        st.write(f"**{label}:** {value}")
    if selected.get("details"):
        st.write("**Details:**")
        st.json(selected["details"])


def _run_option(run_id: int, runs: list[dict[str, Any]]) -> str:
    run = next(item for item in runs if item["run_id"] == run_id)
    return f"#{run_id} · {partition_label(run)} · {status_label(run['status'])}"
