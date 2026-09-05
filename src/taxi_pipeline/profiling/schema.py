"""Deterministic schema descriptions and comparisons."""

import hashlib
import json

import pyarrow as pa


def normalized_schema(schema: pa.Schema) -> list[dict]:
    return [
        {
            "ordinal_position": index,
            "name": field.name,
            "arrow_type": str(field.type),
            "nullable": field.nullable,
        }
        for index, field in enumerate(schema)
    ]


def schema_fingerprint(schema: pa.Schema) -> tuple[list[dict], str]:
    normalized = normalized_schema(schema)
    encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode()
    return normalized, hashlib.sha256(encoded).hexdigest()


def compare_schemas(left: pa.Schema, right: pa.Schema, left_sha: str, right_sha: str) -> dict:
    left_by_name = {field.name: field for field in left}
    right_by_name = {field.name: field for field in right}
    common = [name for name in left.names if name in right_by_name]
    return {
        "schema_sha256": {"yellow_2024_12": left_sha, "yellow_2025_01": right_sha},
        "columns_common": common,
        "columns_only_in_yellow_2024_12": [n for n in left.names if n not in right_by_name],
        "columns_only_in_yellow_2025_01": [n for n in right.names if n not in left_by_name],
        "type_differences": [
            {"name": name, "yellow_2024_12": str(left_by_name[name].type),
             "yellow_2025_01": str(right_by_name[name].type)}
            for name in common if left_by_name[name].type != right_by_name[name].type
        ],
        "nullability_differences": [
            {"name": name, "yellow_2024_12": left_by_name[name].nullable,
             "yellow_2025_01": right_by_name[name].nullable}
            for name in common
            if left_by_name[name].nullable != right_by_name[name].nullable
        ],
        "column_order_difference": left.names != right.names,
        "column_order": {"yellow_2024_12": left.names, "yellow_2025_01": right.names},
        "cbd_congestion_fee": {
            "yellow_2024_12": "cbd_congestion_fee" in left.names,
            "yellow_2025_01": "cbd_congestion_fee" in right.names,
        },
    }
