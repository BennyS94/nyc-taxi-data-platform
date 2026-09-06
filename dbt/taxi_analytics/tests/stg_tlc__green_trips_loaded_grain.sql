with raw_counts as (
    select raw._source_file_id as source_file_id, count(*) as row_count
    from {{ source('tlc_raw', 'green_trips') }} as raw
    inner join {{ source('platform_ops', 'source_files') }} as source_file
        on raw._source_file_id = source_file.source_file_id
    where source_file.dataset_name = 'green_tripdata'
      and source_file.service_type = 'green'
      and source_file.status = 'loaded'
    group by 1
),

staging_counts as (
    select source_file_id, count(*) as row_count
    from {{ ref('stg_tlc__green_trips') }}
    group by 1
)

select
    coalesce(raw_counts.source_file_id, staging_counts.source_file_id) as source_file_id,
    raw_counts.row_count as raw_row_count,
    staging_counts.row_count as staging_row_count
from raw_counts
full outer join staging_counts
    on raw_counts.source_file_id = staging_counts.source_file_id
where raw_counts.row_count is distinct from staging_counts.row_count
