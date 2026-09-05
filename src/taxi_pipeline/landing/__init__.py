"""Immutable local landing-file acquisition and inspection."""

from taxi_pipeline.landing.downloader import ensure_local
from taxi_pipeline.landing.metadata import inspect_source

__all__ = ["ensure_local", "inspect_source"]
