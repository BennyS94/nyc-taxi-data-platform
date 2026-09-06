with loaded_yellow_sources as (
    select source_file_id
    from {{ source('platform_ops', 'source_files') }}
    where dataset_name = 'yellow_tripdata'
      and service_type = 'yellow'
      and status = 'loaded'
)

select
    cast('yellow' as text) as service_type,
    raw."VendorID" as vendor_id,
    raw.tpep_pickup_datetime as pickup_datetime,
    raw.tpep_dropoff_datetime as dropoff_datetime,
    raw.passenger_count,
    raw.trip_distance as trip_distance_miles,
    raw."RatecodeID" as rate_code_id,
    raw.store_and_fwd_flag,
    raw."PULocationID" as pickup_location_id,
    raw."DOLocationID" as dropoff_location_id,
    raw.payment_type,
    cast(null as bigint) as trip_type,
    raw.fare_amount,
    raw.extra as extra_amount,
    raw.mta_tax as mta_tax_amount,
    raw.tip_amount,
    raw.tolls_amount,
    raw.improvement_surcharge as improvement_surcharge_amount,
    raw.congestion_surcharge as congestion_surcharge_amount,
    raw."Airport_fee" as airport_fee_amount,
    raw.cbd_congestion_fee as cbd_congestion_fee_amount,
    raw.total_amount,
    raw._source_file_id as source_file_id,
    raw._source_row_number as source_row_number,
    raw._pipeline_run_id as pipeline_run_id,
    raw._ingested_at as ingested_at
from {{ source('tlc_raw', 'yellow_trips') }} as raw
inner join loaded_yellow_sources as loaded
    on raw._source_file_id = loaded.source_file_id
