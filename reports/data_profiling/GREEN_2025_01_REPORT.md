# Green Taxi January 2025 Profiling Report

This report records targeted observations from the official Green Taxi January 2025 Parquet source. Observations support the Phase 09 contract; they do not filter rows.

## Source identity

- URL: `https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2025-01.parquet`
- Landing path: `data/landing/green/2025/01.parquet`
- Rows: 48,326
- Bytes: 1,178,451
- SHA-256: `84f3a121667157efcbf012c3566a6065df6f8e0312c678cb2f29cd72cc9c0f10`
- Schema SHA-256: `2b19cd71a35a13818165d602b7ece04499a0c9a43ba8e04074102eefad458165`

## Physical schema

| # | Source column | Arrow type | Nullable | Null count | Null rate |
|---:|---|---|---|---:|---:|
| 0 | `VendorID` | `int32` | True | 0 | 0.000000% |
| 1 | `lpep_pickup_datetime` | `timestamp[us]` | True | 0 | 0.000000% |
| 2 | `lpep_dropoff_datetime` | `timestamp[us]` | True | 0 | 0.000000% |
| 3 | `store_and_fwd_flag` | `large_string` | True | 1,836 | 3.799197% |
| 4 | `RatecodeID` | `int64` | True | 1,836 | 3.799197% |
| 5 | `PULocationID` | `int32` | True | 0 | 0.000000% |
| 6 | `DOLocationID` | `int32` | True | 0 | 0.000000% |
| 7 | `passenger_count` | `int64` | True | 1,836 | 3.799197% |
| 8 | `trip_distance` | `double` | True | 0 | 0.000000% |
| 9 | `fare_amount` | `double` | True | 0 | 0.000000% |
| 10 | `extra` | `double` | True | 0 | 0.000000% |
| 11 | `mta_tax` | `double` | True | 0 | 0.000000% |
| 12 | `tip_amount` | `double` | True | 0 | 0.000000% |
| 13 | `tolls_amount` | `double` | True | 0 | 0.000000% |
| 14 | `ehail_fee` | `double` | True | 48,326 | 100.000000% |
| 15 | `improvement_surcharge` | `double` | True | 0 | 0.000000% |
| 16 | `total_amount` | `double` | True | 0 | 0.000000% |
| 17 | `payment_type` | `int64` | True | 1,836 | 3.799197% |
| 18 | `trip_type` | `int64` | True | 1,843 | 3.813682% |
| 19 | `congestion_surcharge` | `double` | True | 1,836 | 3.799197% |
| 20 | `cbd_congestion_fee` | `double` | True | 1,836 | 3.799197% |

## Observed code domains

| Column | Null count | Observed value counts |
|---|---:|---|
| `VendorID` | 0 | `1`: 6,272, `2`: 42,054 |
| `RatecodeID` | 1,836 | `1`: 44,409, `2`: 100, `3`: 26, `4`: 41, `5`: 1,906, `6`: 1, `99`: 7 |
| `store_and_fwd_flag` | 1,836 | `N`: 46,339, `Y`: 151 |
| `payment_type` | 1,836 | `1`: 34,635, `2`: 11,424, `3`: 332, `4`: 98, `5`: 1 |
| `trip_type` | 1,843 | `1`: 44,680, `2`: 1,803 |

## Relevant anomaly evidence

- Pickup outside January 2025: 43
- Dropoff before pickup: 0
- Exact duplicate excess rows: 0
- `trip_distance` below zero: 0; equal to zero: 2,671
- `fare_amount` below zero: 150; equal to zero: 41
- `total_amount` below zero: 153; equal to zero: 33

## Taxi Zone referential coverage

- `PULocationID`: 48,326 matched, 0 unmatched, 0 null
- `DOLocationID`: 48,326 matched, 0 unmatched, 0 null

## Contract conclusion

The observed nullable schema can be preserved source-faithfully in raw and mapped into the existing canonical trip model. Green-only `ehail_fee` remains preserved in raw; `trip_type` and `cbd_congestion_fee` map directly, while the canonical airport fee is null because Green does not supply one.
