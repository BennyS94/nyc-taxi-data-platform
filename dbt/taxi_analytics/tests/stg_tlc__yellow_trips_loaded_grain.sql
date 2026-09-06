with loaded_sources as (
    select source_file_id
    from {{ source('platform_ops', 'source_files') }}
    where dataset_name = 'yellow_tripdata'
      and service_type = 'yellow'
      and status = 'loaded'
),
raw_counts as (
    select
        loaded.source_file_id,
        count(raw._source_row_number) as row_count
    from loaded_sources as loaded
    left join {{ source('tlc_raw', 'yellow_trips') }} as raw
        on loaded.source_file_id = raw._source_file_id
    group by 1
),
staging_counts as (
    select
        source_file_id,
        count(*) as row_count
    from {{ ref('stg_tlc__yellow_trips') }}
    group by 1
)

select
    raw_counts.source_file_id,
    raw_counts.row_count as raw_row_count,
    coalesce(staging_counts.row_count, 0) as staging_row_count
from raw_counts
left join staging_counts using (source_file_id)
where raw_counts.row_count != coalesce(staging_counts.row_count, 0)
