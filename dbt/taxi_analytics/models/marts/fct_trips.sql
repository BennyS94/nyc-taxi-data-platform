{{
    config(
        materialized='incremental',
        unique_key=['source_file_id', 'source_row_number'],
        incremental_strategy='delete+insert',
        indexes=[{'columns': ['pickup_date_key', 'service_type'], 'type': 'btree'}],
        post_hook='analyze {{ this }}'
    )
}}

with trips as (
    select *
    from {{ ref('int_trips_enriched') }}

    {% if is_incremental() %}
    where source_file_id not in (
        select distinct source_file_id
        from {{ this }}
    )
    {% endif %}
)

select
    trips.service_type,
    coalesce(pickup_date.date_key, 0) as pickup_date_key,
    coalesce(dropoff_date.date_key, 0) as dropoff_date_key,
    coalesce(pickup_zone.zone_key, 0) as pickup_zone_key,
    coalesce(dropoff_zone.zone_key, 0) as dropoff_zone_key,
    coalesce(vendor.vendor_key, 0) as vendor_key,
    trips.pickup_datetime,
    trips.dropoff_datetime,
    trips.trip_duration_seconds,
    trips.passenger_count,
    trips.trip_distance_miles,
    trips.rate_code_id,
    coalesce(rate_code.rate_code_name, 'Unknown') as rate_code_name,
    trips.payment_type,
    coalesce(payment.payment_type_name, 'Unknown') as payment_type_name,
    trips.trip_type,
    trips.fare_amount,
    trips.extra_amount,
    trips.mta_tax_amount,
    trips.tip_amount,
    trips.tolls_amount,
    trips.improvement_surcharge_amount,
    trips.congestion_surcharge_amount,
    trips.airport_fee_amount,
    trips.cbd_congestion_fee_amount,
    trips.total_amount,
    trips.source_file_id,
    trips.source_row_number,
    trips.pipeline_run_id
from trips
left join {{ ref('dim_date') }} as pickup_date
    on trips.pickup_date = pickup_date.full_date
left join {{ ref('dim_date') }} as dropoff_date
    on trips.dropoff_date = dropoff_date.full_date
left join {{ ref('dim_zone') }} as pickup_zone
    on trips.pickup_location_id = pickup_zone.location_id
left join {{ ref('dim_zone') }} as dropoff_zone
    on trips.dropoff_location_id = dropoff_zone.location_id
left join {{ ref('dim_vendor') }} as vendor
    on trips.vendor_id = vendor.vendor_id
left join {{ ref('tlc_rate_codes') }} as rate_code
    on trips.rate_code_id = rate_code.rate_code_id
left join {{ ref('tlc_payment_types') }} as payment
    on trips.payment_type = payment.payment_type
