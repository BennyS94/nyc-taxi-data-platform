"""Deterministic JSON and Markdown report output."""

import json
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def markdown_report(yellow_profiles: list[dict], zones: dict, comparison: dict) -> str:
    old, new = yellow_profiles
    lines = [
        "# NYC TLC Data Profiling Report", "", "## Scope", "",
        (
            "This report profiles the official Yellow Taxi December 2024 and January 2025 "
            "Parquet files and the official Taxi Zone Lookup. Results are factual observations; "
            "they do not define production contracts or quality thresholds."
        ), "",
        "## Source File Identity", "", "| Source | Rows | Bytes | SHA-256 |", "|---|---:|---:|---|",
    ]
    for profile in [old, new, zones]:
        file = profile["file"]
        label = _source_label(file)
        lines.append(f"| {label} | {file['row_count']:,} | {file['file_size_bytes']:,} | `{file['checksum_sha256']}` |")
    lines.extend([""])
    for profile, heading in ((old, "Yellow 2024-12 Schema"), (new, "Yellow 2025-01 Schema")):
        lines.extend([f"## {heading}", "", "| # | Source column | Arrow type | Nullable |", "|---:|---|---|---|"])
        for col in profile["schema"]["normalized"]:
            lines.append(f"| {col['ordinal_position']} | `{col['name']}` | `{col['arrow_type']}` | {col['nullable']} |")
        lines.append("")
    lines.extend(["## Schema Comparison", ""])
    lines.append(_schema_observation(comparison))
    lines.extend(["", "## Nullability", "", _null_table(old, new), "",
                  "## Observed Code Domains", "", _domain_table(old, new), "",
                  "## Numeric Distributions", "", _numeric_table(old, new), "",
                  "## Datetime and Duration Observations", "", _datetime_table(old, new), "",
                  "## Taxi Zone Lookup", ""])
    loc = zones["location_id"]
    lines.append(
        f"The lookup has {zones['file']['row_count']:,} rows and {loc['unique_count']:,} distinct "
        f"non-null LocationID values ({loc['duplicate_count']:,} duplicate IDs). Its LocationID "
        f"range is {loc['minimum']} to {loc['maximum']}. Exact full-row duplicate statistics "
        "appear below."
    )
    lines.extend(["", _lookup_domains(zones), "", "## Taxi Zone Referential Coverage", "",
                  _reference_table(old, new), "", "## Exact Duplicate Source Rows", "",
                  _duplicate_table(old, new, zones), "", "## Notable Factual Observations", ""])
    duration_old = old["datetimes"]["trip_duration_seconds"]
    duration_new = new["datetimes"]["trip_duration_seconds"]
    lines.extend([
        "- `cbd_congestion_fee` is absent in December 2024 and present in January 2025.",
        (f"- Pickup timestamps outside the nominal month total "
         f"{duration_old['pickup_outside_nominal_month_count']:,} in December and "
         f"{duration_new['pickup_outside_nominal_month_count']:,} in January."),
        (f"- Rows with dropoff before pickup total {duration_old['dropoff_before_pickup_count']:,} "
         f"in December and {duration_new['dropoff_before_pickup_count']:,} in January."), "",
        "## Open Decisions for Architecture Review", "",
        "- Select PostgreSQL types from the observed Arrow types and value distributions.",
        "- Decide which observed columns form the baseline required source contract.",
        "- Decide which fields, including `cbd_congestion_fee`, are optional or additive.",
        ("- Review observed domains, nulls, datetime anomalies, zone misses, and exact duplicate "
         "rows as candidates for later quality checks."),
        "- Approve any anomaly thresholds only after reviewing these distributions.", "",
    ])
    return "\n".join(lines)


def _source_label(file: dict) -> str:
    return f"Yellow {file['year']:04}-{file['month']:02}" if file["year"] else "Taxi Zone Lookup"


def _schema_observation(comparison: dict) -> str:
    return (
        f"Schema fingerprints are `{comparison['schema_sha256']['yellow_2024_12']}` for December "
        f"and `{comparison['schema_sha256']['yellow_2025_01']}` for January. "
        f"Columns only in December: {comparison['columns_only_in_yellow_2024_12']}. "
        f"Columns only in January: {comparison['columns_only_in_yellow_2025_01']}. "
        f"Type differences: {comparison['type_differences']}. Nullability differences: "
        f"{comparison['nullability_differences']}. Column order differs: "
        f"{comparison['column_order_difference']}."
    )


def _null_table(old: dict, new: dict) -> str:
    lines = ["| Source | Column | Null count | Null rate |", "|---|---|---:|---:|"]
    for profile in (old, new):
        label = _source_label(profile["file"])
        for col in profile["columns"]:
            lines.append(f"| {label} | `{col['name']}` | {col['null_count']:,} | {col['null_rate']:.6%} |")
    return "\n".join(lines)


def _domain_table(old: dict, new: dict) -> str:
    lines = ["| Source | Column | Null count | Observed value counts |", "|---|---|---:|---|"]
    for profile in (old, new):
        for name, result in profile["observed_domains"].items():
            values = ", ".join(f"`{item['value']}`: {item['count']:,}" for item in result["values"])
            lines.append(f"| {_source_label(profile['file'])} | `{name}` | {result['null_count']:,} | {values} |")
    return "\n".join(lines)


def _numeric_table(old: dict, new: dict) -> str:
    lines = ["| Source | Column | Nulls | Min | p01 | p50 | p95 | p99 | Max | < 0 | = 0 | > 0 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for profile in (old, new):
        for name, item in profile["numeric_distributions"].items():
            values = [_display(item[key]) for key in ("minimum", "p01", "p50", "p95", "p99", "maximum")]
            lines.append(f"| {_source_label(profile['file'])} | `{name}` | {item['null_count']:,} | "
                         + " | ".join(values) + f" | {item['count_lt_0']:,} | {item['count_eq_0']:,} | {item['count_gt_0']:,} |")
    return "\n".join(lines)


def _datetime_table(old: dict, new: dict) -> str:
    lines = ["| Source | Pickup min | Pickup max | Dropoff min | Dropoff max | Duration min (s) | p50 | p99 | max |",
             "|---|---|---|---|---|---:|---:|---:|---:|"]
    for profile in (old, new):
        dates, duration = profile["datetimes"], profile["datetimes"]["trip_duration_seconds"]
        lines.append(f"| {_source_label(profile['file'])} | {dates['tpep_pickup_datetime']['minimum']} | "
                     f"{dates['tpep_pickup_datetime']['maximum']} | {dates['tpep_dropoff_datetime']['minimum']} | "
                     f"{dates['tpep_dropoff_datetime']['maximum']} | {_display(duration['minimum'])} | "
                     f"{_display(duration['p50'])} | {_display(duration['p99'])} | {_display(duration['maximum'])} |")
    return "\n".join(lines)


def _lookup_domains(zones: dict) -> str:
    lines = ["| Column | Null count | Observed value counts |", "|---|---:|---|"]
    for name, result in zones["observed_domains"].items():
        values = ", ".join(f"`{item['value']}`: {item['count']:,}" for item in result["values"])
        lines.append(f"| `{name}` | {result['null_count']:,} | {values} |")
    return "\n".join(lines)


def _reference_table(old: dict, new: dict) -> str:
    lines = ["| Source | Field | Null | Matched | Unmatched | Unmatched rate | Unmatched IDs |",
             "|---|---|---:|---:|---:|---:|---|"]
    for profile in (old, new):
        for name, item in profile["taxi_zone_references"].items():
            ids = ", ".join(f"`{x['value']}`: {x['count']:,}" for x in item["unmatched_ids"]) or "None"
            lines.append(f"| {_source_label(profile['file'])} | `{name}` | {item['null_count']:,} | "
                         f"{item['matched_count']:,} | {item['unmatched_count']:,} | "
                         f"{item['unmatched_rate_among_non_null']:.6%} | {ids} |")
    return "\n".join(lines)


def _duplicate_table(*profiles: dict) -> str:
    lines = ["| Source | Total | Unique full rows | Participating rows | Excess rows | Groups |",
             "|---|---:|---:|---:|---:|---:|"]
    for profile in profiles:
        item = profile["exact_duplicate_source_rows"]
        lines.append(f"| {_source_label(profile['file'])} | {item['total_rows']:,} | "
                     f"{item['unique_full_rows']:,} | {item['rows_participating_in_duplicate_groups']:,} | "
                     f"{item['duplicate_excess_rows']:,} | {item['duplicate_groups']:,} |")
    return "\n".join(lines)


def _display(value) -> str:
    return "null" if value is None else f"{value:.6g}" if isinstance(value, float) else str(value)
