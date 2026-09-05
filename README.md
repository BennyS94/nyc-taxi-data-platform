# NYC TLC Data Pipeline & Quality Platform

Phase 01 profiles official NYC TLC Yellow Taxi trip records for December 2024 and
January 2025, plus the Taxi Zone Lookup. The generated reports capture source identity,
physical schemas, nulls, observed domains, numeric and datetime distributions, zone
reference coverage, and exact duplicate source-row counts.

The observed January schema adds `cbd_congestion_fee`; the remaining common columns have
the same Arrow types as December. The source files contain 3,668,371 December rows and
3,475,226 January rows. Full findings and unresolved design questions are in
[`reports/data_profiling/PROFILING_REPORT.md`](reports/data_profiling/PROFILING_REPORT.md).

Install the profiling dependencies and run the complete profile with:

```bash
python -m pip install -e ".[dev]"
python scripts/profile_tlc_data.py
```

The command downloads source files into the Git-ignored `data/landing/` directory and
reuses them on subsequent runs. It regenerates deterministic JSON and Markdown reports.
