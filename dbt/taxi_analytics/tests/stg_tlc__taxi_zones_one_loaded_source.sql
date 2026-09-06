-- depends_on: {{ ref('stg_tlc__taxi_zones') }}

with loaded_source_count as (
    select count(*) as source_count
    from {{ source('platform_ops', 'source_files') }}
    where partition_key = 'reference/taxi_zones'
      and dataset_name = 'taxi_zone_lookup'
      and status = 'loaded'
)

select source_count
from loaded_source_count
where source_count != 1
