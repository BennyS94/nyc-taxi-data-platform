with loaded_taxi_zone_source as (
    select source_file_id
    from {{ source('platform_ops', 'source_files') }}
    where partition_key = 'reference/taxi_zones'
      and dataset_name = 'taxi_zone_lookup'
      and status = 'loaded'
)

select
    raw."LocationID" as location_id,
    raw."Borough" as borough,
    raw."Zone" as zone_name,
    raw.service_zone,
    raw._source_file_id as source_file_id,
    raw._source_row_number as source_row_number,
    raw._pipeline_run_id as pipeline_run_id,
    raw._ingested_at as ingested_at
from {{ source('tlc_raw', 'taxi_zones') }} as raw
inner join loaded_taxi_zone_source as loaded
    on raw._source_file_id = loaded.source_file_id
