"""Run the complete Phase 01 TLC data profile."""

import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from taxi_pipeline.profiling.lookup import profile_taxi_zones
from taxi_pipeline.profiling.parquet import profile_yellow
from taxi_pipeline.profiling.report import markdown_report, write_json
from taxi_pipeline.profiling.schema import compare_schemas
from taxi_pipeline.sources.tlc import SOURCES, ensure_local


def main() -> None:
    labels = ("yellow 2024-12", "yellow 2025-01", "Taxi Zone Lookup")
    for source, label in zip(SOURCES, labels):
        path = ensure_local(source, ROOT)
        print(f"Using {label}: {path.relative_to(ROOT)}")
    print("Profiling Taxi Zone Lookup...")
    zones, zone_ids = profile_taxi_zones(SOURCES[2], ROOT)
    yellow = []
    for source, label in zip(SOURCES[:2], labels[:2]):
        print(f"Profiling {label}...")
        yellow.append(profile_yellow(source, ROOT, zone_ids))
    print("Comparing schemas...")
    schemas = [pq.ParquetFile(ROOT / source.landing_path).schema_arrow for source in SOURCES[:2]]
    comparison = compare_schemas(
        schemas[0], schemas[1], yellow[0]["schema"]["schema_sha256"],
        yellow[1]["schema"]["schema_sha256"],
    )
    output = ROOT / "reports/data_profiling"
    write_json(output / "yellow_2024_12_profile.json", yellow[0])
    write_json(output / "yellow_2025_01_profile.json", yellow[1])
    write_json(output / "taxi_zones_profile.json", zones)
    write_json(output / "schema_comparison.json", comparison)
    (output / "PROFILING_REPORT.md").write_text(
        markdown_report(yellow, zones, comparison), encoding="utf-8"
    )
    print("Reports written to reports/data_profiling/")


if __name__ == "__main__":
    main()
