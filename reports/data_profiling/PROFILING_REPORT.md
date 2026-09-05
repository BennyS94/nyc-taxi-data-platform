# NYC TLC Data Profiling Report

## Scope

This report profiles the official Yellow Taxi December 2024 and January 2025 Parquet files and the official Taxi Zone Lookup. Results are factual observations; they do not define production contracts or quality thresholds.

## Source File Identity

| Source | Rows | Bytes | SHA-256 |
|---|---:|---:|---|
| Yellow 2024-12 | 3,668,371 | 61,524,085 | `41ebf7db80bebde60c58e5143c14cdf38ad04a0f3e3ff44215b3e240d55f6c78` |
| Yellow 2025-01 | 3,475,226 | 59,158,238 | `9af277e4c0d3f9deb30644da822981e1e7df6af58313170fd3aa8a474485488a` |
| Taxi Zone Lookup | 265 | 12,331 | `1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed` |

## Yellow 2024-12 Schema

| # | Source column | Arrow type | Nullable |
|---:|---|---|---|
| 0 | `VendorID` | `int32` | True |
| 1 | `tpep_pickup_datetime` | `timestamp[us]` | True |
| 2 | `tpep_dropoff_datetime` | `timestamp[us]` | True |
| 3 | `passenger_count` | `int64` | True |
| 4 | `trip_distance` | `double` | True |
| 5 | `RatecodeID` | `int64` | True |
| 6 | `store_and_fwd_flag` | `large_string` | True |
| 7 | `PULocationID` | `int32` | True |
| 8 | `DOLocationID` | `int32` | True |
| 9 | `payment_type` | `int64` | True |
| 10 | `fare_amount` | `double` | True |
| 11 | `extra` | `double` | True |
| 12 | `mta_tax` | `double` | True |
| 13 | `tip_amount` | `double` | True |
| 14 | `tolls_amount` | `double` | True |
| 15 | `improvement_surcharge` | `double` | True |
| 16 | `total_amount` | `double` | True |
| 17 | `congestion_surcharge` | `double` | True |
| 18 | `Airport_fee` | `double` | True |

## Yellow 2025-01 Schema

| # | Source column | Arrow type | Nullable |
|---:|---|---|---|
| 0 | `VendorID` | `int32` | True |
| 1 | `tpep_pickup_datetime` | `timestamp[us]` | True |
| 2 | `tpep_dropoff_datetime` | `timestamp[us]` | True |
| 3 | `passenger_count` | `int64` | True |
| 4 | `trip_distance` | `double` | True |
| 5 | `RatecodeID` | `int64` | True |
| 6 | `store_and_fwd_flag` | `large_string` | True |
| 7 | `PULocationID` | `int32` | True |
| 8 | `DOLocationID` | `int32` | True |
| 9 | `payment_type` | `int64` | True |
| 10 | `fare_amount` | `double` | True |
| 11 | `extra` | `double` | True |
| 12 | `mta_tax` | `double` | True |
| 13 | `tip_amount` | `double` | True |
| 14 | `tolls_amount` | `double` | True |
| 15 | `improvement_surcharge` | `double` | True |
| 16 | `total_amount` | `double` | True |
| 17 | `congestion_surcharge` | `double` | True |
| 18 | `Airport_fee` | `double` | True |
| 19 | `cbd_congestion_fee` | `double` | True |

## Schema Comparison

Schema fingerprints are `a4ec3c7b9c38f45205b807a5d5246227351321bd6069b1e4ba3fd67c02871674` for December and `d2b38a269f98178feaf927bdfb2e837852d1ebb72afdb3b08c86f8f32967998b` for January. Columns only in December: []. Columns only in January: ['cbd_congestion_fee']. Type differences: []. Nullability differences: []. Column order differs: False.

## Nullability

| Source | Column | Null count | Null rate |
|---|---|---:|---:|
| Yellow 2024-12 | `VendorID` | 0 | 0.000000% |
| Yellow 2024-12 | `tpep_pickup_datetime` | 0 | 0.000000% |
| Yellow 2024-12 | `tpep_dropoff_datetime` | 0 | 0.000000% |
| Yellow 2024-12 | `passenger_count` | 326,291 | 8.894711% |
| Yellow 2024-12 | `trip_distance` | 0 | 0.000000% |
| Yellow 2024-12 | `RatecodeID` | 326,291 | 8.894711% |
| Yellow 2024-12 | `store_and_fwd_flag` | 326,291 | 8.894711% |
| Yellow 2024-12 | `PULocationID` | 0 | 0.000000% |
| Yellow 2024-12 | `DOLocationID` | 0 | 0.000000% |
| Yellow 2024-12 | `payment_type` | 0 | 0.000000% |
| Yellow 2024-12 | `fare_amount` | 0 | 0.000000% |
| Yellow 2024-12 | `extra` | 0 | 0.000000% |
| Yellow 2024-12 | `mta_tax` | 0 | 0.000000% |
| Yellow 2024-12 | `tip_amount` | 0 | 0.000000% |
| Yellow 2024-12 | `tolls_amount` | 0 | 0.000000% |
| Yellow 2024-12 | `improvement_surcharge` | 0 | 0.000000% |
| Yellow 2024-12 | `total_amount` | 0 | 0.000000% |
| Yellow 2024-12 | `congestion_surcharge` | 326,291 | 8.894711% |
| Yellow 2024-12 | `Airport_fee` | 326,291 | 8.894711% |
| Yellow 2025-01 | `VendorID` | 0 | 0.000000% |
| Yellow 2025-01 | `tpep_pickup_datetime` | 0 | 0.000000% |
| Yellow 2025-01 | `tpep_dropoff_datetime` | 0 | 0.000000% |
| Yellow 2025-01 | `passenger_count` | 540,149 | 15.542845% |
| Yellow 2025-01 | `trip_distance` | 0 | 0.000000% |
| Yellow 2025-01 | `RatecodeID` | 540,149 | 15.542845% |
| Yellow 2025-01 | `store_and_fwd_flag` | 540,149 | 15.542845% |
| Yellow 2025-01 | `PULocationID` | 0 | 0.000000% |
| Yellow 2025-01 | `DOLocationID` | 0 | 0.000000% |
| Yellow 2025-01 | `payment_type` | 0 | 0.000000% |
| Yellow 2025-01 | `fare_amount` | 0 | 0.000000% |
| Yellow 2025-01 | `extra` | 0 | 0.000000% |
| Yellow 2025-01 | `mta_tax` | 0 | 0.000000% |
| Yellow 2025-01 | `tip_amount` | 0 | 0.000000% |
| Yellow 2025-01 | `tolls_amount` | 0 | 0.000000% |
| Yellow 2025-01 | `improvement_surcharge` | 0 | 0.000000% |
| Yellow 2025-01 | `total_amount` | 0 | 0.000000% |
| Yellow 2025-01 | `congestion_surcharge` | 540,149 | 15.542845% |
| Yellow 2025-01 | `Airport_fee` | 540,149 | 15.542845% |
| Yellow 2025-01 | `cbd_congestion_fee` | 0 | 0.000000% |

## Observed Code Domains

| Source | Column | Null count | Observed value counts |
|---|---|---:|---|
| Yellow 2024-12 | `VendorID` | 0 | `1`: 829,242, `2`: 2,838,485, `6`: 414, `7`: 230 |
| Yellow 2024-12 | `RatecodeID` | 326,291 | `1`: 3,126,642, `2`: 115,805, `3`: 12,448, `4`: 8,916, `5`: 36,147, `6`: 6, `99`: 42,116 |
| Yellow 2024-12 | `store_and_fwd_flag` | 326,291 | `N`: 3,324,497, `Y`: 17,583 |
| Yellow 2024-12 | `payment_type` | 0 | `0`: 326,291, `1`: 2,733,369, `2`: 490,651, `3`: 28,938, `4`: 89,122 |
| Yellow 2025-01 | `VendorID` | 0 | `1`: 753,671, `2`: 2,719,860, `6`: 489, `7`: 1,206 |
| Yellow 2025-01 | `RatecodeID` | 540,149 | `1`: 2,756,472, `2`: 94,420, `3`: 8,622, `4`: 7,092, `5`: 26,501, `6`: 7, `99`: 41,963 |
| Yellow 2025-01 | `store_and_fwd_flag` | 540,149 | `N`: 2,927,431, `Y`: 7,646 |
| Yellow 2025-01 | `payment_type` | 0 | `0`: 540,149, `1`: 2,444,393, `2`: 390,429, `3`: 23,773, `4`: 76,481, `5`: 1 |

## Numeric Distributions

| Source | Column | Nulls | Min | p01 | p50 | p95 | p99 | Max | < 0 | = 0 | > 0 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Yellow 2024-12 | `passenger_count` | 326,291 | 0 | 1 | 1 | 3 | 5 | 9 | 0 | 30,397 | 3,311,683 |
| Yellow 2024-12 | `trip_distance` | 0 | 0 | 0 | 1.68 | 13.73 | 19.91 | 328828 | 0 | 75,450 | 3,592,921 |
| Yellow 2024-12 | `fare_amount` | 0 | -975 | -12.8 | 14.2 | 65.87 | 84 | 3033.1 | 78,444 | 2,053 | 3,587,874 |
| Yellow 2024-12 | `total_amount` | 0 | -951 | -17.5 | 21.66 | 82.69 | 106.31 | 3037.1 | 70,496 | 606 | 3,597,269 |
| Yellow 2024-12 | `extra` | 0 | -9.25 | 0 | 1 | 5 | 7.5 | 14.25 | 34,962 | 1,678,503 | 1,954,906 |
| Yellow 2024-12 | `mta_tax` | 0 | -0.5 | -0.5 | 0.5 | 0.5 | 0.5 | 10.5 | 65,953 | 54,338 | 3,548,080 |
| Yellow 2024-12 | `tip_amount` | 0 | -80 | 0 | 2.72 | 11.95 | 18.6 | 471 | 140 | 1,012,706 | 2,655,525 |
| Yellow 2024-12 | `tolls_amount` | 0 | -70.38 | 0 | 0 | 6.94 | 6.94 | 120.15 | 5,890 | 3,390,843 | 271,638 |
| Yellow 2024-12 | `improvement_surcharge` | 0 | -1 | -1 | 1 | 1 | 1 | 1 | 69,040 | 39,285 | 3,560,046 |
| Yellow 2024-12 | `congestion_surcharge` | 326,291 | -2.5 | -2.5 | 2.5 | 2.5 | 2.5 | 2.5 | 57,770 | 256,876 | 3,027,434 |
| Yellow 2024-12 | `Airport_fee` | 326,291 | -1.75 | 0 | 0 | 1.75 | 1.75 | 1.75 | 10,114 | 3,077,038 | 254,928 |
| Yellow 2025-01 | `passenger_count` | 540,149 | 0 | 1 | 1 | 3 | 5 | 9 | 0 | 24,656 | 2,910,421 |
| Yellow 2025-01 | `trip_distance` | 0 | 0 | 0 | 1.67 | 11.83 | 19.5 | 276424 | 0 | 90,893 | 3,384,333 |
| Yellow 2025-01 | `fare_amount` | 0 | -900 | -10.7 | 12.11 | 52 | 72.3 | 863372 | 144,118 | 1,398 | 3,329,710 |
| Yellow 2025-01 | `total_amount` | 0 | -901 | -15.7 | 19.95 | 74 | 102.92 | 863380 | 63,037 | 559 | 3,411,630 |
| Yellow 2025-01 | `extra` | 0 | -7.5 | 0 | 0 | 5 | 7.5 | 15 | 29,596 | 1,764,424 | 1,681,206 |
| Yellow 2025-01 | `mta_tax` | 0 | -0.5 | -0.5 | 0.5 | 0.5 | 0.5 | 10.5 | 57,140 | 38,170 | 3,379,916 |
| Yellow 2025-01 | `tip_amount` | 0 | -86 | 0 | 2.45 | 10 | 17.19 | 400 | 124 | 1,118,008 | 2,357,094 |
| Yellow 2025-01 | `tolls_amount` | 0 | -126.94 | 0 | 0 | 6.94 | 6.94 | 170.94 | 4,559 | 3,259,590 | 211,077 |
| Yellow 2025-01 | `improvement_surcharge` | 0 | -1 | -1 | 1 | 1 | 1 | 1 | 59,530 | 37,694 | 3,378,002 |
| Yellow 2025-01 | `congestion_surcharge` | 540,149 | -2.5 | -2.5 | 2.5 | 2.5 | 2.5 | 2.5 | 48,321 | 225,938 | 2,660,818 |
| Yellow 2025-01 | `Airport_fee` | 540,149 | -1.75 | 0 | 0 | 1.75 | 1.75 | 6.75 | 10,411 | 2,706,446 | 218,220 |
| Yellow 2025-01 | `cbd_congestion_fee` | 0 | -0.75 | 0 | 0.75 | 0.75 | 0.75 | 0.75 | 6,553 | 1,222,178 | 2,246,495 |

## Datetime and Duration Observations

| Source | Pickup min | Pickup max | Dropoff min | Dropoff max | Duration min (s) | p50 | p99 | max |
|---|---|---|---|---|---:|---:|---:|---:|
| Yellow 2024-12 | 2008-12-31T23:03:59 | 2025-03-23T20:42:06 | 2009-01-01T00:30:36 | 2025-03-23T22:52:56 | -2514 | 827 | 4675 | 359535 |
| Yellow 2025-01 | 2024-12-31T20:47:55 | 2025-02-01T00:00:44 | 2024-12-18T07:52:40 | 2025-02-01T23:44:11 | -3088339 | 702 | 3535 | 337579 |

## Taxi Zone Lookup

The lookup has 265 rows and 265 distinct non-null LocationID values (0 duplicate IDs). Its LocationID range is 1 to 265. Exact full-row duplicate statistics appear below.

| Column | Null count | Observed value counts |
|---|---:|---|
| `Borough` | 1 | `Bronx`: 43, `Brooklyn`: 61, `EWR`: 1, `Manhattan`: 69, `Queens`: 69, `Staten Island`: 20, `Unknown`: 1 |
| `service_zone` | 2 | `Airports`: 2, `Boro Zone`: 205, `EWR`: 1, `Yellow Zone`: 55 |

## Taxi Zone Referential Coverage

| Source | Field | Null | Matched | Unmatched | Unmatched rate | Unmatched IDs |
|---|---|---:|---:|---:|---:|---|
| Yellow 2024-12 | `PULocationID` | 0 | 3,668,371 | 0 | 0.000000% | None |
| Yellow 2024-12 | `DOLocationID` | 0 | 3,668,371 | 0 | 0.000000% | None |
| Yellow 2025-01 | `PULocationID` | 0 | 3,475,226 | 0 | 0.000000% | None |
| Yellow 2025-01 | `DOLocationID` | 0 | 3,475,226 | 0 | 0.000000% | None |

## Exact Duplicate Source Rows

| Source | Total | Unique full rows | Participating rows | Excess rows | Groups |
|---|---:|---:|---:|---:|---:|
| Yellow 2024-12 | 3,668,371 | 3,668,371 | 0 | 0 | 0 |
| Yellow 2025-01 | 3,475,226 | 3,475,226 | 0 | 0 | 0 |
| Taxi Zone Lookup | 265 | 265 | 0 | 0 | 0 |

## Notable Factual Observations

- `cbd_congestion_fee` is absent in December 2024 and present in January 2025.
- Pickup timestamps outside the nominal month total 34 in December and 22 in January.
- Rows with dropoff before pickup total 99 in December and 124 in January.

## Open Decisions for Architecture Review

- Select PostgreSQL types from the observed Arrow types and value distributions.
- Decide which observed columns form the baseline required source contract.
- Decide which fields, including `cbd_congestion_fee`, are optional or additive.
- Review observed domains, nulls, datetime anomalies, zone misses, and exact duplicate rows as candidates for later quality checks.
- Approve any anomaly thresholds only after reviewing these distributions.
