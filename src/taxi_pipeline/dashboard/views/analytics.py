"""Filtered warehouse analytics view."""

from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from taxi_pipeline.dashboard.components import (
    format_decimal,
    format_integer,
    format_money,
    loaded_date_bounds,
    monthly_frame,
    render_empty,
    render_metrics,
)

Loader = Callable[..., Any]


def render(load: Loader) -> None:
    st.title("Trip Analytics")
    sources = load("list_all_sources")
    date_bounds = loaded_date_bounds(sources)
    if date_bounds is None:
        render_empty("No analytics data is available for filtering.")
        return
    first, last = date_bounds

    service_label = st.selectbox("Service Type", ["All", "Yellow", "Green"])
    selected_dates = st.date_input("Date Range", value=(first, last), min_value=first, max_value=last)
    top_n = st.slider("Top N Zones", min_value=5, max_value=25, value=10, step=5)
    if not isinstance(selected_dates, tuple) or len(selected_dates) != 2:
        render_empty("Select both a start and end date.")
        return

    service_type = None if service_label == "All" else service_label.lower()
    params = {
        "service_type": service_type,
        "start_date": selected_dates[0],
        "end_date": selected_dates[1],
    }
    summary = load("analytics_summary", **params)
    monthly = monthly_frame(load("analytics_monthly", **params))
    zones = pd.DataFrame(load("analytics_zones", **params, limit=top_n))

    render_metrics(
        [
            ("Trip Count", format_integer(summary["trip_count"])),
            ("Total Amount", format_money(summary["total_amount"])),
            ("Average Fare", format_money(summary["average_fare_amount"])),
            ("Average Tip", format_money(summary["average_tip_amount"])),
            (
                "Average Trip Distance",
                format_decimal(summary["average_trip_distance_miles"], " mi"),
            ),
        ]
    )
    if monthly.empty:
        render_empty("No analytics data for the selected range.")
        return

    left, right = st.columns(2)
    with left:
        st.subheader("Trips by Month")
        st.bar_chart(
            monthly.pivot_table(
                index="month", columns="service_type", values="trip_count", aggfunc="sum"
            )
        )
        st.subheader("Average Trip Distance by Month")
        st.line_chart(
            monthly.pivot_table(
                index="month",
                columns="service_type",
                values="average_trip_distance_miles",
                aggfunc="mean",
            )
        )
    with right:
        st.subheader("Average Fare by Month")
        st.line_chart(
            monthly.pivot_table(
                index="month",
                columns="service_type",
                values="average_fare_amount",
                aggfunc="mean",
            )
        )
        st.subheader("Top Pickup Zones")
        if zones.empty:
            render_empty("No pickup-zone data for the selected range.")
        else:
            zones["label"] = zones["borough"] + " · " + zones["zone_name"]
            st.bar_chart(zones.set_index("label")[["trip_count"]], horizontal=True)
