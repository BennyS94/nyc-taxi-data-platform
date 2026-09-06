{{ config(materialized='table') }}

with observed_dates as (
    select pickup_date as full_date
    from {{ ref('int_trips_enriched') }}
    where pickup_date is not null

    union

    select dropoff_date as full_date
    from {{ ref('int_trips_enriched') }}
    where dropoff_date is not null
),

known_dates as (
    select
        to_char(full_date, 'YYYYMMDD')::integer as date_key,
        full_date,
        extract(year from full_date)::integer as year,
        extract(quarter from full_date)::integer as quarter,
        extract(month from full_date)::integer as month,
        to_char(full_date, 'FMMonth') as month_name,
        extract(day from full_date)::integer as day,
        extract(isodow from full_date)::integer as day_of_week,
        to_char(full_date, 'FMDay') as day_name,
        extract(isodow from full_date) in (6, 7) as is_weekend
    from observed_dates
)

select
    cast(0 as integer) as date_key,
    cast(null as date) as full_date,
    cast(null as integer) as year,
    cast(null as integer) as quarter,
    cast(null as integer) as month,
    cast(null as text) as month_name,
    cast(null as integer) as day,
    cast(null as integer) as day_of_week,
    cast(null as text) as day_name,
    cast(null as boolean) as is_weekend

union all

select *
from known_dates
