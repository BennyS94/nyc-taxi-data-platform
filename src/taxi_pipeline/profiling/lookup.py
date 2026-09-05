"""Taxi Zone Lookup profiling."""

from pathlib import Path

import pandas as pd
import pyarrow as pa

from taxi_pipeline.profiling.statistics import dataframe_duplicate_profile, domain_profile
from taxi_pipeline.sources.tlc import Source, file_identity


def profile_taxi_zones(source: Source, root: Path) -> tuple[dict, set]:
    frame = pd.read_csv(root / source.landing_path)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    row_count = len(frame)
    columns = [
        {
            "ordinal_position": index, "name": name,
            "pandas_type": str(frame[name].dtype), "arrow_type": str(table.schema.field(name).type),
            "null_count": int(frame[name].isna().sum()),
            "null_rate": float(frame[name].isna().mean()) if row_count else 0.0,
        }
        for index, name in enumerate(frame.columns)
    ]
    location = frame["LocationID"]
    numeric_location = pd.to_numeric(location, errors="coerce")
    profile = {
        "file": {**file_identity(source, root), "row_count": row_count,
                 "column_names": frame.columns.tolist()},
        "columns": columns,
        "location_id": {
            "duplicate_count": int(location.duplicated().sum()),
            "unique_count": int(location.nunique(dropna=True)),
            "minimum": _native(numeric_location.min()), "maximum": _native(numeric_location.max()),
        },
        "observed_domains": {
            name: domain_profile(table.column(name))
            for name in ("Borough", "service_zone") if name in frame.columns
        },
        "exact_duplicate_source_rows": dataframe_duplicate_profile(frame),
    }
    return profile, set(location.dropna().tolist())


def _native(value):
    return None if pd.isna(value) else value.item() if hasattr(value, "item") else value
