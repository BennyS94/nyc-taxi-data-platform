"""Platform overview view."""

from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from taxi_pipeline.dashboard.components import (
    format_integer,
    monthly_frame,
    render_empty,
    render_metrics,
)

Loader = Callable[..., Any]


def render(load: Loader) -> None:
    st.title("NYC TLC Data Platform")
    st.caption("End-to-end data engineering platform for NYC Yellow and Green Taxi data.")

    total = load("analytics_summary")
    yellow = load("analytics_summary", service_type="yellow")
    green = load("analytics_summary", service_type="green")
    sources = load("list_all_sources")
    runs = load("list_all_runs")
    warning_checks = sum(run.get("warning_count") or 0 for run in runs)

    render_metrics(
        [
            ("Total Trips", format_integer(total["trip_count"])),
            ("Yellow Trips", format_integer(yellow["trip_count"])),
            ("Green Trips", format_integer(green["trip_count"])),
            ("Loaded Source Files", format_integer(sum(s["status"] == "loaded" for s in sources))),
            ("Successful Pipeline Runs", format_integer(sum(r["status"] == "succeeded" for r in runs))),
            ("Quality Warnings", format_integer(warning_checks)),
        ]
    )
    st.caption("Quality Warnings counts violated WARNING checks recorded across pipeline runs.")

    monthly = monthly_frame(load("analytics_monthly"))
    zones = pd.DataFrame(load("analytics_zones", limit=10))
    if monthly.empty:
        render_empty("No analytics data is available yet.")
        return

    left, right = st.columns(2)
    with left:
        st.subheader("Trips by Month")
        trips = monthly.pivot_table(
            index="month", columns="service_type", values="trip_count", aggfunc="sum"
        )
        st.bar_chart(trips)
        st.subheader("Yellow vs Green Share")
        share = monthly.groupby("service_type", as_index=False)["trip_count"].sum()
        st.bar_chart(share.set_index("service_type"))
    with right:
        st.subheader("Total Amount by Month")
        amounts = monthly.pivot_table(
            index="month", columns="service_type", values="total_amount", aggfunc="sum"
        )
        st.line_chart(amounts)
        st.subheader("Top Pickup Zones")
        if zones.empty:
            render_empty("No pickup-zone analytics are available.")
        else:
            zones["label"] = zones["borough"] + " · " + zones["zone_name"]
            st.bar_chart(zones.set_index("label")[["trip_count"]], horizontal=True)
