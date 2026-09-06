with canonical_counts as (
    select source_file_id, count(*) as row_count
    from {{ ref('int_trips_normalized') }}
    group by 1
),

fact_counts as (
    select source_file_id, count(*) as row_count
    from {{ ref('fct_trips') }}
    group by 1
)

select
    coalesce(canonical_counts.source_file_id, fact_counts.source_file_id) as source_file_id,
    canonical_counts.row_count as canonical_row_count,
    fact_counts.row_count as fact_row_count
from canonical_counts
full outer join fact_counts
    on canonical_counts.source_file_id = fact_counts.source_file_id
where canonical_counts.row_count is distinct from fact_counts.row_count
