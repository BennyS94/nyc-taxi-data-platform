"""Shared display helpers for dashboard pages."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

STATUS_MARKERS = {
    "succeeded": "✓ SUCCEEDED",
    "failed": "✕ FAILED",
    "skipped": "– SKIPPED",
    "running": "… RUNNING",
    "loaded": "✓ LOADED",
    "revision_detected": "! REVISION DETECTED",
}


def status_label(value: str | None) -> str:
    normalized = (value or "unknown").lower()
    return STATUS_MARKERS.get(normalized, normalized.upper())


def partition_label(item: dict[str, Any]) -> str:
    service = item.get("service_type") or item.get("dataset_name") or "source"
    year = item.get("source_year")
    month = item.get("source_month")
    return f"{service} {year:04d}-{month:02d}" if year and month else str(service)


def format_integer(value: Any) -> str:
    return f"{int(value or 0):,}"


def format_money(value: Any) -> str:
    return "—" if value is None else f"${float(value):,.2f}"


def format_decimal(value: Any, suffix: str = "") -> str:
    return "—" if value is None else f"{float(value):,.2f}{suffix}"


def format_percentage(value: Any) -> str:
    return "—" if value is None else f"{float(value) * 100:.4f}%"


def duration_label(started_at: str | None, finished_at: str | None) -> str:
    if not started_at:
        return "—"
    if not finished_at:
        return "In progress"
    start = datetime.fromisoformat(started_at)
    finish = datetime.fromisoformat(finished_at)
    seconds = max(0, int((finish - start).total_seconds()))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def monthly_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["month"] = frame["month"].fillna("Unknown")
    return frame


def render_empty(message: str) -> None:
    st.info(message)


def render_metrics(metrics: list[tuple[str, str]]) -> None:
    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics, strict=True):
        column.metric(label, value)
