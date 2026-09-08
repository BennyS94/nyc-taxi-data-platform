"""Streamlit entrypoint for the read-only platform dashboard."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import streamlit as st

from taxi_pipeline.dashboard.api_client import APIClient, APIClientError
from taxi_pipeline.dashboard.pages import analytics, overview, pipeline, quality

DEFAULT_API_BASE_URL = "http://localhost:8000"


@st.cache_data(ttl=45, show_spinner=False)
def _cached_call(
    base_url: str,
    method_name: str,
    args: tuple[Any, ...],
    kwargs: tuple[tuple[str, Any], ...],
) -> Any:
    client = APIClient(base_url)
    return getattr(client, method_name)(*args, **dict(kwargs))


def _loader(base_url: str) -> Callable[..., Any]:
    def load(method_name: str, *args: Any, **kwargs: Any) -> Any:
        return _cached_call(base_url, method_name, args, tuple(sorted(kwargs.items())))

    return load


def main() -> None:
    st.set_page_config(page_title="NYC TLC Data Platform", page_icon="🚕", layout="wide")
    base_url = os.environ.get("API_BASE_URL", DEFAULT_API_BASE_URL)

    with st.sidebar:
        st.header("NYC TLC Platform")
        page_name = st.radio(
            "Navigate",
            ["Overview", "Trip Analytics", "Pipeline Monitoring", "Data Quality"],
        )
        if st.button("Refresh data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        st.markdown("**Read-only presentation layer**")
        st.caption("Streamlit → FastAPI → PostgreSQL ops + dbt marts")
        st.caption(f"API: {base_url}")

    pages = {
        "Overview": overview.render,
        "Trip Analytics": analytics.render,
        "Pipeline Monitoring": pipeline.render,
        "Data Quality": quality.render,
    }
    try:
        pages[page_name](_loader(base_url))
    except APIClientError as error:
        st.error(str(error))
        st.info("Confirm API_BASE_URL and start FastAPI before refreshing the dashboard.")


if __name__ == "__main__":
    main()
