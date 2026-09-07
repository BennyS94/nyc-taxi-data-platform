# ADR: Do not partition at current scale

## Decision

Do not partition either the raw trip tables or `marts.fct_trips` at the current project
scale. Revisit only after measured growth or maintenance behavior makes the added
complexity worthwhile.

## Context and measurements

The measured warehouse has 7,191,923 facts (1,749 MB heap) and the Yellow raw table has
7,143,597 rows (1,439 MB heap). Full-history monthly aggregation completes in about 2.6
seconds locally. A 48 MB B-tree reduced the selective daily summary from 711 ms to 24 ms
and the daily zone ranking from 818 ms to 111 ms without changing physical table layout.

Raw ingestion sustained roughly 30,500–34,400 rows/second across tested COPY batch sizes.
No measured ingestion, query, vacuum, or migration problem requires partition management.

## Options considered

- Monthly range partitions for raw Yellow and Green tables could prune source months, but
  quality is already scoped by source-file identity and the current primary key provides
  that prefix. Partitioning would complicate migrations and cross-partition uniqueness.
- Monthly range partitions for `fct_trips` could prune selective date queries, but the
  accepted B-tree already provides substantial pruning-like behavior. It would also add
  dbt relation management and incremental-build complexity.
- BRIN offered a low-storage option for the date-correlated fact but measured 683 ms for
  summary and 731 ms for zones, so it was ineffective for these physical page ranges.
- Keeping ordinary tables plus one measured B-tree preserves the simplest ownership,
  lineage, and idempotency model.

## Trade-offs

The chosen design retains full scans for full-history aggregations and exact duplicate
quality grouping. In return it avoids partition creation, routing, migration, pruning
verification, and uniqueness complications. The decision is specific to the measured
local scale and should be revisited if fact size, retention, or maintenance needs change
materially.
