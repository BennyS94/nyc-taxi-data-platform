"""Pipeline and source monitoring page."""

from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from taxi_pipeline.dashboard.components import (
    duration_label,
    format_integer,
    partition_label,
    render_empty,
    render_metrics,
    status_label,
)

Loader = Callable[..., Any]


def render(load: Loader) -> None:
    st.title("Pipeline Monitoring")
    runs = load("list_all_runs")
    sources = load("list_all_sources")

    st.subheader("Recent Pipeline Runs")
    if not runs:
        render_empty("No pipeline runs found.")
    else:
        run_rows = [
            {
                "Run ID": run["run_id"],
                "Service": run.get("service_type") or run["dataset_name"],
                "Partition": partition_label(run),
                "Status": status_label(run["status"]),
                "Rows Loaded": run.get("rows_loaded"),
                "Warnings": run.get("warning_count"),
                "Errors": run.get("error_count"),
                "Started": run["started_at"],
                "Duration": duration_label(run["started_at"], run.get("finished_at")),
            }
            for run in runs
        ]
        st.dataframe(pd.DataFrame(run_rows), hide_index=True, use_container_width=True)
        selected_run_id = st.selectbox(
            "Inspect Run",
            [run["run_id"] for run in runs],
            format_func=lambda value: _run_option(value, runs),
        )
        _render_run_detail(load("get_run", selected_run_id))

    st.subheader("Source Files")
    if not sources:
        render_empty("No source files found.")
        return
    source_rows = [
        {
            "Source File ID": source["source_file_id"],
            "Partition": partition_label(source),
            "Service": source.get("service_type") or source["dataset_name"],
            "Rows": source.get("row_count"),
            "Checksum": f"{source['checksum_sha256'][:12]}…",
            "Status": status_label(source["status"]),
            "Storage Backend": source["storage_backend"],
            "Loaded At": source.get("loaded_at"),
        }
        for source in sources
    ]
    st.dataframe(pd.DataFrame(source_rows), hide_index=True, use_container_width=True)
    selected_source_id = st.selectbox(
        "Inspect Source",
        [source["source_file_id"] for source in sources],
        format_func=lambda value: _source_option(value, sources),
    )
    _render_source_detail(load("get_source", selected_source_id))


def _run_option(run_id: int, runs: list[dict[str, Any]]) -> str:
    run = next(item for item in runs if item["run_id"] == run_id)
    return f"#{run_id} · {partition_label(run)} · {status_label(run['status'])}"


def _source_option(source_id: int, sources: list[dict[str, Any]]) -> str:
    source = next(item for item in sources if item["source_file_id"] == source_id)
    return f"#{source_id} · {partition_label(source)} · {status_label(source['status'])}"


def _render_run_detail(run: dict[str, Any]) -> None:
    st.markdown("#### Run Detail")
    render_metrics(
        [
            ("Run ID", str(run["run_id"])),
            ("Source File ID", str(run.get("source_file_id") or "—")),
            ("Status", status_label(run["status"])),
            ("Rows Read", format_integer(run.get("rows_read"))),
            ("Rows Loaded", format_integer(run.get("rows_loaded"))),
            ("Duration", duration_label(run["started_at"], run.get("finished_at"))),
        ]
    )
    st.write(f"**Partition:** {partition_label(run)}")
    st.write(f"**Reason:** {run.get('status_reason') or '—'}")
    st.write(f"**Started:** {run['started_at']}")
    st.write(f"**Finished:** {run.get('finished_at') or '—'}")
    st.write(
        f"**Warnings / Errors:** {run.get('warning_count') or 0} / {run.get('error_count') or 0}"
    )
    if run.get("error_message"):
        st.error(f"Error: {run['error_message']}")


def _render_source_detail(source: dict[str, Any]) -> None:
    st.markdown("#### Source Detail")
    if source["status"] == "revision_detected":
        st.warning("Source revision detected. Automatic replacement is blocked.")
    details = {
        "Source URL": source["source_url"],
        "Partition": source["partition_key"],
        "Checksum": source["checksum_sha256"],
        "Schema Fingerprint": source.get("schema_fingerprint") or "—",
        "File Size": f"{source['file_size_bytes']:,} bytes",
        "Row Count": format_integer(source.get("row_count")),
        "Status": status_label(source["status"]),
        "Storage Backend": source["storage_backend"],
        "Storage URI": source.get("storage_uri") or "—",
        "Validated At": source.get("validated_at") or "—",
        "Loaded At": source.get("loaded_at") or "—",
    }
    for label, value in details.items():
        st.write(f"**{label}:** {value}")
