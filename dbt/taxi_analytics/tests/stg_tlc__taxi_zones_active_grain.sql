with active_raw as (
    select raw._source_file_id, raw._source_row_number
    from {{ source('tlc_raw', 'taxi_zones') }} as raw
    inner join {{ source('platform_ops', 'source_files') }} as source_file
        on raw._source_file_id = source_file.source_file_id
    where source_file.partition_key = 'reference/taxi_zones'
      and source_file.dataset_name = 'taxi_zone_lookup'
      and source_file.status = 'loaded'
),
counts as (
    select
        (select count(*) from active_raw) as raw_row_count,
        (select count(*) from {{ ref('stg_tlc__taxi_zones') }}) as staging_row_count
)

select raw_row_count, staging_row_count
from counts
where raw_row_count != staging_row_count
