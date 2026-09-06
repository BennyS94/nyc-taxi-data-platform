{{ config(materialized='table') }}

select
    cast(0 as integer) as zone_key,
    cast(null as integer) as location_id,
    cast('Unknown' as text) as borough,
    cast('Unknown' as text) as zone_name,
    cast(null as text) as service_zone

union all

select
    location_id as zone_key,
    location_id,
    borough,
    zone_name,
    service_zone
from {{ ref('stg_tlc__taxi_zones') }}
