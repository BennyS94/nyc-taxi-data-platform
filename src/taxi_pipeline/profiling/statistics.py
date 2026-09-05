"""Column, domain, datetime, reference, and duplicate statistics."""

import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


def _scalar(value):
    value = value.as_py() if isinstance(value, pa.Scalar) else value
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def null_summary(array: pa.ChunkedArray) -> dict:
    total = len(array)
    return {"null_count": array.null_count, "null_rate": array.null_count / total if total else 0.0}


def numeric_profile(array: pa.ChunkedArray) -> dict:
    valid = array.drop_null()
    total = len(array)
    result = {
        "non_null_count": len(valid), **null_summary(array),
        "minimum": None, "p01": None, "p50": None, "p95": None, "p99": None,
        "maximum": None, "count_lt_0": 0, "count_eq_0": 0, "count_gt_0": 0,
    }
    if len(valid):
        quantiles = pc.quantile(valid, q=[0.01, 0.5, 0.95, 0.99], interpolation="linear")
        result.update({
            "minimum": _scalar(pc.min(valid)), "p01": _scalar(quantiles[0]),
            "p50": _scalar(quantiles[1]), "p95": _scalar(quantiles[2]),
            "p99": _scalar(quantiles[3]), "maximum": _scalar(pc.max(valid)),
            "count_lt_0": _scalar(pc.sum(pc.less(valid, 0))),
            "count_eq_0": _scalar(pc.sum(pc.equal(valid, 0))),
            "count_gt_0": _scalar(pc.sum(pc.greater(valid, 0))),
        })
    assert result["non_null_count"] + result["null_count"] == total
    return result


def domain_profile(array: pa.ChunkedArray) -> dict:
    counts = pc.value_counts(array.drop_null()).to_pylist()
    values = sorted(counts, key=lambda item: (str(type(item["values"])), str(item["values"])))
    return {
        "null_count": array.null_count,
        "values": [{"value": _scalar(item["values"]), "count": item["counts"]} for item in values],
    }


def datetime_profile(array: pa.ChunkedArray) -> dict:
    valid = array.drop_null()
    return {
        **null_summary(array),
        "minimum": _scalar(pc.min(valid)) if len(valid) else None,
        "maximum": _scalar(pc.max(valid)) if len(valid) else None,
    }


def duration_profile(pickup: pa.ChunkedArray, dropoff: pa.ChunkedArray,
                     year: int, month: int) -> dict:
    duration_raw = pc.subtract(dropoff, pickup)
    units_per_second = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}
    duration = pc.divide(pc.cast(duration_raw, pa.int64()), units_per_second[duration_raw.type.unit])
    values = numeric_profile(duration)
    start = pd.Timestamp(year=year, month=month, day=1)
    end = start + pd.offsets.MonthBegin(1)
    outside = pc.and_(pc.is_valid(pickup), pc.or_(pc.less(pickup, start), pc.greater_equal(pickup, end)))
    values.update({
        "dropoff_before_pickup_count": values["count_lt_0"],
        "either_datetime_null_count": _scalar(pc.sum(pc.or_(pc.is_null(pickup), pc.is_null(dropoff)))),
        "pickup_outside_nominal_month_count": _scalar(pc.sum(outside)),
    })
    return values


def zone_reference_profile(array: pa.ChunkedArray, valid_ids: set) -> dict:
    counts = Counter(array.drop_null().to_pylist())
    matched = sum(count for value, count in counts.items() if value in valid_ids)
    unmatched = sorted(
        ({"value": _scalar(value), "count": count} for value, count in counts.items()
         if value not in valid_ids), key=lambda item: item["value"]
    )
    non_null = len(array) - array.null_count
    unmatched_count = non_null - matched
    return {
        "total_rows": len(array), "null_count": array.null_count, "non_null_count": non_null,
        "matched_count": matched, "unmatched_count": unmatched_count,
        "unmatched_rate_among_non_null": unmatched_count / non_null if non_null else 0.0,
        "unmatched_ids": unmatched,
    }


def exact_duplicate_profile(path: Path, batch_size: int = 100_000) -> dict:
    parquet = pq.ParquetFile(path)
    hashes = []
    total = 0
    for batch in parquet.iter_batches(batch_size=batch_size):
        frame = batch.to_pandas()
        hashes.append(pd.util.hash_pandas_object(frame, index=False).to_numpy())
        total += len(frame)
    all_hashes = np.concatenate(hashes) if hashes else np.array([], dtype=np.uint64)
    unique_hashes, hash_counts = np.unique(all_hashes, return_counts=True)
    candidates = set(unique_hashes[hash_counts > 1].tolist())
    groups = defaultdict(Counter)
    if candidates:
        for batch in parquet.iter_batches(batch_size=batch_size):
            frame = batch.to_pandas()
            batch_hashes = pd.util.hash_pandas_object(frame, index=False).to_numpy()
            for index in np.flatnonzero(np.isin(batch_hashes, list(candidates))):
                # Equality is checked on complete, normalized source rows within each hash bucket.
                row = tuple(_duplicate_value(value) for value in frame.iloc[index].tolist())
                groups[int(batch_hashes[index])][row] += 1
    exact_counts = [count for bucket in groups.values() for count in bucket.values() if count > 1]
    excess = sum(count - 1 for count in exact_counts)
    return {
        "total_rows": total, "unique_full_rows": total - excess,
        "rows_participating_in_duplicate_groups": sum(exact_counts),
        "duplicate_excess_rows": excess, "duplicate_groups": len(exact_counts),
    }


def dataframe_duplicate_profile(frame: pd.DataFrame) -> dict:
    duplicate_mask = frame.duplicated(keep=False)
    excess = int(frame.duplicated().sum())
    group_count = int(frame.loc[duplicate_mask].drop_duplicates().shape[0])
    return {
        "total_rows": len(frame), "unique_full_rows": len(frame) - excess,
        "rows_participating_in_duplicate_groups": int(duplicate_mask.sum()),
        "duplicate_excess_rows": excess, "duplicate_groups": group_count,
    }


def _duplicate_value(value):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return ("null",)
    if isinstance(value, pd.Timestamp):
        return ("timestamp", value.isoformat())
    if isinstance(value, np.generic):
        value = value.item()
    return (type(value).__name__, value)
