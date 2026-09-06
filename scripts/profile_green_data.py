"""Generate the targeted Phase 09 Green Taxi baseline profile."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from taxi_pipeline.landing.downloader import ensure_local
from taxi_pipeline.profiling.green import profile_green
from taxi_pipeline.profiling.lookup import profile_taxi_zones
from taxi_pipeline.profiling.report import green_markdown_report, write_json
from taxi_pipeline.sources import green_trip_source, taxi_zone_source


def main() -> None:
    green = green_trip_source(2025, 1)
    zones = taxi_zone_source()
    ensure_local(green, ROOT)
    ensure_local(zones, ROOT)
    _, zone_ids = profile_taxi_zones(zones, ROOT)
    profile = profile_green(green, ROOT, zone_ids)
    output = ROOT / "reports" / "data_profiling"
    write_json(output / "green_2025_01_profile.json", profile)
    (output / "GREEN_2025_01_REPORT.md").write_text(
        green_markdown_report(profile), encoding="utf-8"
    )
    print("Green profile written to reports/data_profiling/")


if __name__ == "__main__":
    main()
