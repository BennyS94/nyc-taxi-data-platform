"""Measure representative FastAPI request latency without a network load tool."""

import argparse
import json
import statistics
import time

from fastapi.testclient import TestClient

from taxi_pipeline.api.app import create_app

ENDPOINTS = (
    "/analytics/summary?service_type=yellow&start_date=2025-01-15&end_date=2025-01-15",
    "/analytics/monthly",
    "/analytics/zones?service_type=yellow&start_date=2025-01-15&end_date=2025-01-15",
    "/runs?limit=50",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=5)
    args = parser.parse_args()
    client = TestClient(create_app())
    results = {}
    for endpoint in ENDPOINTS:
        timings = []
        for _ in range(args.requests):
            started = time.perf_counter()
            response = client.get(endpoint)
            response.raise_for_status()
            timings.append((time.perf_counter() - started) * 1_000)
        ordered = sorted(timings)
        results[endpoint] = {
            "median_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 3),
        }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
